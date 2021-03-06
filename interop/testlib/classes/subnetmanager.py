#!/usr/bin/python3

import re

class SubnetManagerInitializationError(Exception):
    """ Custom initialization exception
    """
    pass

class SubnetManagerParsingError(Exception):
    """ In case the subnet manager output is parsed incorrectly
    """
    pass

class SubnetManager:
    def __init__(self, node=None):
        """ Represents the subnet manager
        """
        self.node = node
        if not self.node:
            raise SubnetManagerInitializationError("Must initialize SubnetManager object with node")
        self.stored_state = None

    def start(self):
        """ Starts the subnet manager at ip address
        """
        if self.node.is_up():
            output = self.node.command("systemctl start opensm")
            if output[1].strip():
                print(output[1])
            return True
        else:
            return False

    def stop(self):
        """ Stop the subnet manager at ip address
        """
        if self.node.is_up():
            output= self.node.command("systemctl stop opensm")
            if output[1].strip():
                print(output[1])
            return True
        else:
            return False

    def status(self):
        """ Status of the subnet manager at the ip address
        """
        self.ip = self.node.ethif.ip
        if self.node.is_up():
            # opensm for status
            output = self.node.command("systemctl status opensm")

            if output[1].strip():
                print(output[1])
            active_lines = []
            for line in output[0].split('\n'):
                if "Active: " in line:
                    active_lines.append(line)
            if len(active_lines) != 1:
                if not active_lines:
                    self.stored_state = 'inactive'
                else:
                    raise SubnetManagerParsingError("the output of `systemctl status opensm` was parsed incorrectly on {}".format(self.node.ethif.id))
            else:
                self.stored_state = active_lines[0].strip().split()[1]
            return self.stored_state
        return False

    def print(self):
        """ Print the the subnet manager status
        """
        print("Untracked" if not self.stored_state else self.stored_state)

def validate():
    SubnetManager().print()

if __name__ == "__main__":
    validate()

