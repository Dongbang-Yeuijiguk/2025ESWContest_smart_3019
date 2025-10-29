// csi_saver.c - 최소 버전 (CSV 저장 없음, 초반 N개 스킵, 표준 termios만 사용)
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <time.h>
#include <termios.h>   // 표준 termios만!
#include <strings.h>   // strcasecmp
#include <curl/curl.h>

#define SERIAL_DEV     "/dev/ttyUSB0"   // 포트 확인 후 변경
#define BAUDRATE       3000000          // 시스템이 지원해야 함. 안되면 921600 등으로
#define SKIP_COUNT     5                // 초반 N개는 버림

// InfluxDB 2.x
#define INFLUX_HOST    "http://localhost"
#define INFLUX_PORT    8086
#define INFLUX_ORG     "YOUR_ORG"       // TODO
#define INFLUX_BUCKET  "YOUR_BUCKET"    // TODO
#define INFLUX_TOKEN   "YOUR_TOKEN"     // TODO

#define READ_CHUNK     (64*1024)
#define LBUF_CAP       (1<<20)

static volatile sig_atomic_t RUN = 1;
static int fd_ser = -1;
static CURL* curlh = NULL;

// ── 시그널
static void on_sig(int s){ (void)s; RUN = 0; }

// ── 숫자(정수) 판별
static int is_num(const char* s){
    if(!s || !*s) return 0;
    if(*s=='+'||*s=='-') s++;
    int d=0; while(*s){ if(*s<'0'||*s>'9') return 0; d=1; s++; }
    return d;
}

// ── CSV split(따옴표 지원)
static int csv_split(char* line, char* tok[], int maxn){
    int n=0,inq=0; char* p=line; char* st=p;
    while(*p && n<maxn){
        char c=*p;
        if(c=='"') inq=!inq;
        else if(c==',' && !inq){ *p='\0'; tok[n++]=st; st=p+1; }
        p++;
    }
    if(n<maxn && st) tok[n++]=st;
    for(int i=0;i<n;i++){
        char* s=tok[i];
        while(*s==' '||*s=='\t'||*s=='\r'||*s=='\n') s++;
        char* e=s+strlen(s);
        while(e>s && (e[-1]==' '||e[-1]=='\t'||e[-1]=='\r'||e[-1]=='\n')) e--;
        *e='\0';
        if(e-s>=2 && s[0]=='"' && e[-1]=='"'){ s++; e--; *e='\0'; }
        tok[i]=s;
    }
    return n;
}

// ── Line Protocol 태그 이스케이프
static void esc_tag(char* out,size_t cap,const char* in){
    size_t j=0;
    for(size_t i=0; in&&in[i]&&j+2<cap; i++){
        char c=in[i];
        if(c==' '||c==','||c=='=') out[j++]='\\';
        out[j++]=c;
    }
    out[j]='\0';
}

// ── CURL write 콜백 (응답 버리기) ⇒ C 함수로!
static size_t sink_cb(char* ptr, size_t size, size_t nmemb, void* userdata){
    (void)ptr; (void)userdata;
    return size*nmemb;
}

// ── Influx 초기화/전송/정리
static int influx_init(void){
    if (curl_global_init(CURL_GLOBAL_ALL) != 0) return -1;
    curlh = curl_easy_init();
    if(!curlh) return -1;

    char url[512];
    snprintf(url,sizeof(url), "%s:%d/api/v2/write?org=%s&bucket=%s&precision=ms",
             INFLUX_HOST, INFLUX_PORT, INFLUX_ORG, INFLUX_BUCKET);
    curl_easy_setopt(curlh, CURLOPT_URL, url);
    curl_easy_setopt(curlh, CURLOPT_POST, 1L);

    struct curl_slist* hdr=NULL; char auth[1024];
    snprintf(auth,sizeof(auth),"Authorization: Token %s", INFLUX_TOKEN);
    hdr = curl_slist_append(hdr, auth);
    hdr = curl_slist_append(hdr, "Content-Type: text/plain; charset=utf-8");
    curl_easy_setopt(curlh, CURLOPT_HTTPHEADER, hdr);

    curl_easy_setopt(curlh, CURLOPT_WRITEFUNCTION, sink_cb); // ✅ 람다 대신 C 함수

    return 0;
}
static int influx_post(const char* body,size_t len){
    curl_easy_setopt(curlh, CURLOPT_POSTFIELDS, body);
    curl_easy_setopt(curlh, CURLOPT_POSTFIELDSIZE, (long)len);
    CURLcode rc = curl_easy_perform(curlh);
    if(rc!=CURLE_OK) return -1;
    long code=0; curl_easy_getinfo(curlh, CURLINFO_RESPONSE_CODE, &code);
    return (code>=200 && code<300) ? 0 : -1;
}
static void influx_cleanup(void){
    if(curlh){ curl_easy_cleanup(curlh); curlh=NULL; }
    curl_global_cleanup();
}

// ── 시리얼: 공통 설정 + 표준 보레이트만
static int set_serial_common(int fd){
    struct termios tio;
    if(tcgetattr(fd,&tio)<0) return -1;
    cfmakeraw(&tio);
    tio.c_cflag |= (CLOCAL|CREAD);
    tio.c_cflag &= ~CSTOPB;
    tio.c_cflag &= ~CRTSCTS;
    tio.c_cflag &= ~PARENB;
    tio.c_cflag &= ~CSIZE; tio.c_cflag |= CS8;
    tio.c_iflag &= ~(IXON|IXOFF|IXANY);
    tio.c_cc[VMIN]=1; tio.c_cc[VTIME]=0;
    return tcsetattr(fd,TCSANOW,&tio);
}
static int set_baud_std(int fd, int baud){
    struct termios t;
    if(tcgetattr(fd,&t)<0) return -1;

    speed_t spd = B115200;
    switch(baud){
        case 115200: spd=B115200; break;
#ifdef B921600
        case 921600: spd=B921600; break;
#endif
#ifdef B2000000
        case 2000000: spd=B2000000; break;
#endif
#ifdef B3000000
        case 3000000: spd=B3000000; break;
#endif
        default:     spd=B115200; break; // 지원 안 하면 115200으로
    }
    if(cfsetispeed(&t, spd)<0) return -1;
    if(cfsetospeed(&t, spd)<0) return -1;
    if(tcsetattr(fd, TCSANOW, &t)<0) return -1;
    return 0;
}
static int open_serial(const char* dev,int baud){
    int fd = open(dev, O_RDONLY|O_NOCTTY|O_NONBLOCK);
    if(fd<0) return -1;
    if(set_serial_common(fd)<0){ close(fd); return -1; }
    if(set_baud_std(fd, baud)<0){ close(fd); return -1; }
    int fl = fcntl(fd,F_GETFL); fcntl(fd,F_SETFL, fl & ~O_NONBLOCK); // 블로킹
    return fd;
}

// ── CSV → Line Protocol → POST
static void send_lp(char* t[], int n){
    if(n<16) return;
    const char* type = t[0];
    const char* seq  = t[1];
    const char* mac  = t[2];
    const char* rssi = t[3];
    const char* rate = t[4];
    const char* nf   = t[5];
    const char* fft  = t[6];
    const char* agc  = t[7];
    const char* ch   = t[8];
    // t[9] local_ts
    const char* sig  = t[10];
    const char* rxst = t[11];
    const char* rts  = t[12];
    const char* rts2 = t[13]; // real_timestamp
    const char* len  = t[14];
    const char* fw   = t[15];

    char type_e[128], mac_e[128], ch_e[64];
    esc_tag(type_e,sizeof(type_e), type?type:"");
    esc_tag(mac_e, sizeof(mac_e),  mac?mac:"");
    esc_tag(ch_e,  sizeof(ch_e),   ch?ch:"");

    char lp[2048]; size_t pos=0;
    pos += snprintf(lp+pos,sizeof(lp)-pos,
        "csi,type=%s,mac=%s,channel=%s ", type_e, mac_e, ch_e);

#define F(key,val) do{ if((val)&&is_num(val)) pos+=snprintf(lp+pos,sizeof(lp)-pos,"%s=%si,",key,val); }while(0)
    F("seq",seq); F("rssi",rssi); F("rate",rate); F("noise_floor",nf);
    F("fft_gain",fft); F("agc_gain",agc); F("sig_len",sig);
    F("rx_state",rxst); F("real_time_set",rts); F("real_timestamp",rts2);
    F("len",len); F("first_word",fw);
    if(pos>0 && lp[pos-1]==',') lp[pos-1]=' ';

    long long ts_ms;
    if(rts2 && is_num(rts2)){
        ts_ms = strtoll(rts2,NULL,10);
        // real_timestamp가 초 단위면 아래 주석 해제
        // ts_ms *= 1000;
    }else{
        struct timespec ts; clock_gettime(CLOCK_REALTIME,&ts);
        ts_ms = (long long)ts.tv_sec*1000LL + ts.tv_nsec/1000000LL;
    }
    pos += snprintf(lp+pos,sizeof(lp)-pos," %lld\n", ts_ms);

    influx_post(lp, pos);
}

int main(void){
    signal(SIGINT, on_sig);
    signal(SIGTERM,on_sig);

    if(influx_init()<0) return 1;

    fd_ser = open_serial(SERIAL_DEV, BAUDRATE);
    if(fd_ser<0){ influx_cleanup(); return 1; }

    char* rbuf=(char*)malloc(READ_CHUNK);
    char* lbuf=(char*)malloc(LBUF_CAP);
    if(!rbuf||!lbuf){ if(rbuf)free(rbuf); if(lbuf)free(lbuf); close(fd_ser); influx_cleanup(); return 1; }

    size_t lsize=0; unsigned long long lines=0;

    while(RUN){
        ssize_t n = read(fd_ser, rbuf, READ_CHUNK);
        if(n<=0){ if(errno==EINTR) continue; usleep(1000); continue; }
        for(ssize_t i=0;i<n;i++){
            if(lsize<LBUF_CAP-1) lbuf[lsize++] = rbuf[i];
            if(rbuf[i]=='\n'){
                while(lsize>0 && (lbuf[lsize-1]=='\r'||lbuf[lsize-1]=='\n')) lsize--;
                lbuf[lsize]='\0';

                lines++;
                if(lines>SKIP_COUNT){
                    char tmp[LBUF_CAP];
                    size_t len=strlen(lbuf); if(len>=sizeof(tmp)) len=sizeof(tmp)-1;
                    memcpy(tmp,lbuf,len); tmp[len]='\0';
                    char* tok[32]; int nt = csv_split(tmp,tok,32);
                    if(!(nt>=1 && strcasecmp(tok[0],"type")==0)){
                        send_lp(tok,nt);
                    }
                }
                lsize=0;
            }
        }
    }

    free(rbuf); free(lbuf);
    close(fd_ser);
    influx_cleanup();
    return 0;
}
