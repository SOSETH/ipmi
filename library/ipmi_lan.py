#!/usr/bin/python3

# Copyright: (c) 2019, Maximilian Falkenstein <maximilian.falkenstein@sos.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ipmi_lan

short_description: Configure IPMI LAN interface(s)

version_added: "2.4"

description:
    - This module supports configuring an IPMI's LAN interfaces using the in-band transport, that is, by connecting
      directly to an IPMI via `/dev/ipmi0`. This allows for initial provisioning of the IPMI when the network transport
      used by most other ipmi modules is not yet working.

options:
    channel:
        description:
            - Channel id to configure. In most cases, you'll leave this at the default value of `1`, however,
              theoretically, vendors are allowed to change this and IPMIs might even have multiple LAN interfaces.
        required: false
    name:
        description:
            - This is the message to send to the sample module
        required: true
    new:
        description:
            - Control to demo if the result of this module is changed or not
        required: false

author:
    - Maximilian Falkenstein (@uubk)
'''

EXAMPLES = '''
# Set a static IP on channel 1 (the default channel)
- name: Configure network on local BMC
  ipmi_lan:
    channel: 1
    config:
      ip: 172.31.0.210
      netmask: 255.255.255.0
      gateway: 172.31.0.1
      vlan: none

# Enable DHCP instead
- name: Configure network on local BMC
  ipmi_lan:
    channel: 1
    config:
      dhcp: yes
      vlan: 7
'''

RETURN = '''
message:
    description: The output message that the sample module generates
'''

"""
Set in Progress         : Set Complete
Auth Type Support       : NONE MD2 MD5 PASSWORD 
Auth Type Enable        : Callback : MD2 MD5 PASSWORD 
                        : User     : MD2 MD5 PASSWORD 
                        : Operator : MD2 MD5 PASSWORD 
                        : Admin    : MD2 MD5 PASSWORD 
                        : OEM      : MD2 MD5 PASSWORD 
IP Address Source       : Static Address
IP Address              : 192.168.101.10
Subnet Mask             : 255.255.255.0
MAC Address             : 0c:c4:7a:cd:93:31
SNMP Community String   : public
IP Header               : TTL=0x00 Flags=0x00 Precedence=0x00 TOS=0x00
BMC ARP Control         : ARP Responses Enabled, Gratuitous ARP Disabled
Default Gateway IP      : 192.168.101.1
Default Gateway MAC     : fc:ec:da:42:fe:f7
Backup Gateway IP       : 0.0.0.0
Backup Gateway MAC      : 00:00:00:00:00:00
802.1q VLAN ID          : 8
802.1q VLAN Priority    : 0
RMCP+ Cipher Suites     : 1,2,3,6,7,8,11,12
Cipher Suite Priv Max   : XaaaXXaaaXXaaXX
                        :     X=Cipher Suite Unused
                        :     c=CALLBACK
                        :     u=USER
                        :     o=OPERATOR
                        :     a=ADMIN
                        :     O=OEM
Bad Password Threshold  : Not Available
"""
from ansible.module_utils.basic import AnsibleModule

ATTRIBUTE_TO_IPMITOOL_ATTRIBUTE = {
    'ip': 'ipaddr',
    'netmask': 'netmask',
    'gateway': 'defgw ipaddr',
    'vlan': 'vlan id',
}


class LANChannel:
    def __init__(self, module, channel_id, check_mode):
        self.attrs = {}
        self.diff = {'before': {}, 'after': {}}
        self.channel_id = channel_id
        self.changed = False
        self.module = module
        self.check_mode = check_mode

    def load_channel_inband(self):
        _, result, _ = self.module.run_command(["sudo", "ipmitool", "lan", "print", str(self.channel_id)],
                                               check_rc=True)
        self._parse_lan_status(result)

        return self.attrs

    def _parse_lan_status(self, status_str):
        for row in status_str.split('\n'):
            if row.startswith("IP Address Source"):
                self.attrs['dhcp'] = not row.endswith("Static Address")
            if row.startswith("IP Address  "):
                self.attrs['ip'] = row.split(':')[1].strip()
            if row.startswith("Subnet Mask"):
                self.attrs['netmask'] = row.split(':')[1].strip()
            if row.startswith("Default Gateway IP"):
                self.attrs['gateway'] = row.split(':')[1].strip()
            if row.startswith("802.1q VLAN ID"):
                self.attrs['vlan'] = row.split(':')[1].strip().replace('Disabled', 'none')
            if row.startswith("MAC Address"):
                self.attrs['mac'] = row.split(':', 1)[1].strip()

    def _set_channel_attribute(self, attribute, value):
        if not self.check_mode:
            command = ["sudo", "ipmitool", "lan", "set", str(self.channel_id)]
            if attribute.find(' ') is not -1:
                command.extend(attribute.split(' '))
            else:
                command.append(attribute)
            command.append(value)
            self.module.run_command(command, check_rc=True)

    def set_attribute(self, attribute, value):
        if not isinstance(value, bool):
            value = str(value)

        current_value = self.attrs[attribute]
        if current_value != value:
            if attribute in ATTRIBUTE_TO_IPMITOOL_ATTRIBUTE.keys():
                self._set_channel_attribute(ATTRIBUTE_TO_IPMITOOL_ATTRIBUTE[attribute], value)
            elif attribute is 'dhcp':
                self._set_channel_attribute('ipsrc', 'dhcp' if value else 'static')
            else:
                raise NotImplemented

            self.changed = True
            self.diff['before'][attribute] = current_value
            self.diff['after'][attribute] = value


def main():
    module = AnsibleModule(
        argument_spec=dict(
            channel=dict(type='int', required=False, default=1),
            config=dict(type='dict', required=True)
        ),
        supports_check_mode=True
    )

    result = {'changed': False}

    # Load current channel status
    obj = LANChannel(module, module.params['channel'], module.check_mode)
    obj.load_channel_inband()

    if 'ip' in module.params['config']:
        obj.set_attribute('ip', module.params['config']['ip'])
    if 'netmask' in module.params['config']:
        obj.set_attribute('netmask', module.params['config']['netmask'])
    if 'gateway' in module.params['config']:
        obj.set_attribute('gateway', module.params['config']['gateway'])
    if 'vlan' in module.params['config']:
        obj.set_attribute('vlan', module.params['config']['vlan'])
    if 'dhcp' in module.params['config']:
        obj.set_attribute('dhcp', module.params['config']['dhcp'])

    result['changed'] = obj.changed
    if module._diff:
        result['diff'] = obj.diff

    module.exit_json(**result)


if __name__ == '__main__':
    main()

