import Button from '@enact/sandstone/Button';
import kind from '@enact/core/kind';
import Dropdown from '@enact/sandstone/Dropdown';
import Switch from '@enact/sandstone/Switch';

import {Panel, Header} from '@enact/sandstone/Panels';

const MainPanel = kind({
	name: 'MainPanel',

	render: (props) => (
		<Panel {...props}>
			<Header title="Hello world!" />
			<Button>Click me</Button>
			<Dropdown
			inline
			title="Options"
			>
			{['Option 1', 'Option 2', 'Option 3', 'Option 4', 'Option 5']}
			</Dropdown>
			<Switch />​

		</Panel>
	)
});

export default MainPanel;
