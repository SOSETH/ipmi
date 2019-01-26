#!/usr/bin/python

# Copyright: (c) 2019, Maximilian Falkenstein <maximilian.falkenstein@sos.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ipmi_user

short_description: Configure IPMI Users

version_added: "2.4"

description:
    - This module manages IPMI users using the in-band interface, suitable for initial provisioning

options:
    user:
        description:
            - User to modify
        required: true
    channel:
        description:
            - Channel to associate the user with (default: `1`)
    state:
        description:
            - Whether to create the user (`present`, default) or to remove it (`absent`)
        required: false
    password:
        description:
            - Password to set in case the user is created
        required: false

author:
    - Maximilian Falkenstein (@uubk)
'''

EXAMPLES = '''
# Ensure that there is a user ADMIN/ADMIN
- name: Configure network on local BMC
  ipmi_user:
    name: ADMIN
    password: ADMIN
    state: present
'''

RETURN = '''

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


PRIV_NAME_TO_VALUE_MAP = {
    "callback": 1,
    "user": 2,
    "operator": 3,
    "administrator": 4,
    "oem proprietary": 5,
    "no access": 0xf
}


class IPMIUsers():
    def __init__(self, module, channel_id, check_mode):
        self.channel_id = channel_id
        self.check_mode = check_mode
        self.module = module
        self.users_detected = {}
        self.free_ids = []
        self.changed = False

    def load_users_inband(self):
        _, result, _ = self.module.run_command(["sudo", "ipmitool", "user", "list", str(self.channel_id)],
                                               check_rc=True)
        self._parse_user_list(result)

    def _parse_user_list(self, status_str):
        for row in status_str.split('\n'):
            if row.startswith('ID  Name'):
                # Description row
                continue
            if row is '':
                # Empty row
                continue
            if row.endswith('Unknown (0x00)'):
                # Unknown privileges normally indicate that this slot is not occupied
                # Add it to the list of free slots
                row = row.split()
                self.free_ids.extend(row[0])
                continue
            # A row looks like this:
            # 2   ADMIN            false   false      true       ADMINISTRATOR
            row = row.split()
            if len(row) == 5:
                # A user named '' has appeared...
                self.free_ids.extend(row[0])
                continue
            privs = str(row[5])
            if privs.lower() in PRIV_NAME_TO_VALUE_MAP.keys():
                privs = PRIV_NAME_TO_VALUE_MAP[privs.lower()]
            self.users_detected[row[1]] = {
                'id': row[0],
                'name': row[1],
                'Callin': row[2],
                'LinkAuth': row[3],
                'IPMIMsg': row[4],
                'privileges': privs,
            }

    def _set_user_attr(self, args):
        if not self.check_mode:
            command = ["sudo", "ipmitool", "user"]
            command.extend(args)
            self.module.run_command(command, check_rc=True)

    def delete_user(self, name):
        # Actually...you can't really delete an user...
        if name in self.users_detected.keys():
            self.changed = True
            if self.check_mode:
                return

            # Instead of deleting the user, set it's name to the empty string and revoke access...
            uid = self.users_detected[name]['id']
            self._set_user_attr(["priv", str(uid), '0xF', str(self.channel_id)])
            self._set_user_attr(["set", "name", str(uid), ''])

    def add_user(self, name):
        if name not in self.users_detected.keys():
            self.changed = True
            uid = self.free_ids.pop()
            self._set_user_attr(["set", "name", str(uid), name])

    def set_user_password(self, user, password):
        # There is a check password command ... it just takes the uid instead of the name
        if user not in self.users_detected.keys():
            if not self.check_mode:
                # User is new -> refresh data
                self.load_users_inband()
            else:
                # We're in check mode, so let's just assume everything is all right...
                return

        uid = self.users_detected[user]['id']
        rc, _, _ = self.module.run_command(["sudo", "ipmitool", "user", "test", str(uid), "20", password],
                                           check_rc=False)
        if rc == 1:
            # Wrong password
            self._set_user_attr(["set", "password", uid, password, "20"])
            self.changed = True

    def set_user_privs(self, user, privs):
        # privs can be int (good) or string. In the latter case, we need to convert them
        if isinstance(privs, str):
            if privs not in PRIV_NAME_TO_VALUE_MAP.keys():
                return
            privs = PRIV_NAME_TO_VALUE_MAP[privs.lower()]

        if user not in self.users_detected.keys():
            if not self.check_mode:
                # User is new -> refresh data
                self.load_users_inband()
            else:
                # We're in check mode, so let's just assume everything is all right...
                return

        uid = self.users_detected[user]['id']
        if self.users_detected[user]['privileges'] is not privs:
            self._set_user_attr(['priv', str(uid), str(privs), str(self.channel_id)])
            self.changed = True


def run_module():
    module_args = dict(
        channel=dict(type='int', required=False, default=1),
        user=dict(type='str', required=True, no_log=False),
        password=dict(type='str', required=False, no_log=True),
        privileges=dict(type='str', required=False),
        state=dict(type='str', required=False, default='present')
    )
    result = dict(
        changed=False
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    # Load current channel status
    obj = IPMIUsers(module, module.params['channel'], module.check_mode)
    obj.load_users_inband()

    user = module.params['user']
    if module.params['state'] == 'present':
        obj.add_user(user)
        if 'password' in module.params:
            obj.set_user_password(user, module.params['password'])
        if 'privileges' in module.params:
            obj.set_user_privs(user, module.params['privileges'])
    else:
        obj.delete_user(user)

    result['changed'] = obj.changed
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()