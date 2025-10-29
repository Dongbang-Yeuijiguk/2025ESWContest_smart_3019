import axios from 'axios';
const NR_URL = process.env.NR_URL;

export const device_control = async(device_type='',command='',value='')=>{
    try{
        const res = await axios.post(`${NR_URL}/api/v1/control/device`,{
            params: {device_type,command,value},
        });
        return res.data;
    } catch(error){
        console.error('NR 연결 실패',error);
        throw error;
    }
};

export const routine_control = async(routine_type='',command='',value='')=>{
    try{
        const res = await axios.post(`${NR_URL}/api/v1/control/routine`,{
            params: {routine_type,command,value},
        });
        return res.data;
    } catch(error){
        console.error('NR 연결 실패',error);
        throw error;
    }
};