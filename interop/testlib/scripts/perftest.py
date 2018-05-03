import testlib.test as test
import testlib.subtest as subtest
import testlib.classes.network as network
import testlib.streamctl as streamctl

import unicodedata
import socket
import errno
import time
import threading
import statistics

# 13.5 TI RDMA Basic Interop

# Checks for the following:
# Inconsistent prformance levels.
# Incorrect data after completion of RDMA exchanges
# Failure of RDMA operations
# Inability to establish connections between endpoints

# Magic number defines the number of times each individual node is tested as the server for
# each perftest, so the total number of times the test is run is NUM_TIMES * 2
NUM_TIMES = 4

def swap_nodes(node1, node2, test_function):
    """ Runs both nodes as server/client.  Comments areonly passed for fails
    """
    # For a single node pair that is passed into perftest
    # run the test once with each node as server 
    output_list = []
    for i in range(NUM_TIMES):
        output_list.append(test_function(node1, node2))
        output_list.append(test_function(node2, node1))

    count = 0
    sumation = 0
    outputs = []
    for item in output_list:
        for line in item:
            outputs.append(float(line.split()[3]))
            sumation += outputs[-1]
            count +=1

    # Compile test results into a single return value 
    average = sumation/count

    stdev = statistics.stdev(outputs)
    return average,stdev


def get_ib_dev_name(node):
    """ returns the device name as a string
    """
    out=node.command('ibv_devinfo')
    if out[1]:
        sys.stderr.write(out[1])

    # The mess below just gets the device name from the first line of ib_devinfo
    return out[0].split('\n')[0].split()[1]


def is_port_open(node, port):
    """ is the specified port open on this node?
    """
    stdout = node.command("lsof -i :{}".format(port))[0].strip()
    return False if stdout else True


def get_open_port(node, default):
    """ returns the next available port if default isn't open
    """
    port=default
    while(not is_port_open(node, port)):
        print("port: {} is currently in use on node {}".format(port, node.ethif.ip))
        port+=1
    return port


def get_interesting_output(output):
    o = ""
    out_flag = False
    for line in output[0].split('\n'):
        if not line.strip():
            continue
        if line.strip()[0] == "#":
            print(line)
            out_flag = True
            continue
        if out_flag is True:
            out_flag = False
            print(line)
            o+=line
    if output[1]:
        print("errors:\n[{}]".format(output[1]))
    return o


def perftest(command):
    """ This generic test runs the perftest commands
    """

    # Ensure that a subnet manager is running
    def kill_rogues(node,command):
        """ Kill the processes if the thread needs to exit early
        """
        print(node.command("pkill -x {}".format(command))[1])

    def read_bw(server, client,default_port=18515):

        # need to figure out how to check if default port is active 
        available_port = get_open_port(server, default_port)

        # Get the device names 
        device_server = get_ib_dev_name(server)
        device_client = get_ib_dev_name(client)

        # Generage the command
        cmd_server = command.format(device_server, available_port, "")
        cmd_client = command.format(device_client, available_port, server.ibif.ip)

        def cmd(func, command, result, key):
            """ The result dictionary is used for getting returned output from the threads
            """
            result[key] = func(command)

        threads=[]
        results = dict()
        threads.append(threading.Thread(target=cmd, args=[server.command, cmd_server,results,"server"]))
        threads.append(threading.Thread(target=cmd, args=[client.command, cmd_client,results,"client"]))

        print("starting threads:")
        print("on [{}] running: [{}]".format(server.ethif.ip, cmd_server))
        print("on [{}] running: [{}]".format(client.ethif.ip, cmd_client))
        for thread in threads:
            thread.start()
            time.sleep(0.5)

        # The next couple of lines are funky, this allows the KeyboardInterrupt to gracefully exit the threads
        try:
            threads[1].join()
        except KeyboardInterrupt:
            print("Exception got caught, cleaning up processes so that the remote ports, etc are available")
            kill_rogues(server, cmd_server.split()[0])
            kill_rogues(client, cmd_client.split()[0])

            # Output the results  
            print("Printing perftest results")

            # Server 
            out = results['server']
            server_out = get_interesting_output(out)
            print("server: {}".format(server.ethif.ip))

            # Client
            out = results['client']
            client_out = get_interesting_output(out)
            print("client: {}".format(client.ethif.ip))
            raise KeyboardInterrupt

        print("Printing perftest results")

        # Client
        out = results['client']
        print("client: {}".format(client.ethif.ip))
        client_out = get_interesting_output(out)

        try:
            threads[0].join()
        except KeyboardInterrupt:
            print("Exception got caught,killing rogue processes")
            kill_rogues(server, cmd_server.split()[0])
            kill_rogues(client, cmd_client.split()[0])

            # Output the results  
            out = results['server']
            print("server: {}".format(server.ethif.ip))
            get_interesting_output(out)
            raise KeyboardInterrupt

        # Server
        out = results['server']
        print("server: {}".format(server.ethif.ip))
        server_out = get_interesting_output(out)

        time.sleep(1)
        return server_out, client_out

    output = swap_nodes(network.nodes[1],network.nodes[2],read_bw)
    average = "{0:.2f} Gb/s ".format(float(output[0])*8/1000)
    stdev="{:s}({:.3f})".format(unicodedata.lookup("GREEK SMALL LETTER SIGMA"),float(output[1]))
    return [True, "{: >15}{: >10}".format(average, stdev)]


small_test= "-d {} -i 1 -p {} -s 1 -n 25000 -m 2048 {} -F"
large_test= "-d {} -i 1 -p {} -s 1000000 -n 300 -m 2048 {} -F"

subtests=[]
subtests.append(subtest.Subtest(test=perftest, name="Small RDMA Read", number='1',arg='ib_read_bw '+small_test))
subtests.append(subtest.Subtest(test=perftest, name="Large RDMA Read", number='2',arg='ib_read_bw '+large_test))
subtests.append(subtest.Subtest(test=perftest, name="Small RDMA Write", number='3',arg='ib_write_bw '+small_test))
subtests.append(subtest.Subtest(test=perftest, name="Large RDMA Write", number='4',arg='ib_write_bw '+large_test))
subtests.append(subtest.Subtest(test=perftest, name="Small RDMA Send", number='5',arg='ib_send_bw '+small_test))
subtests.append(subtest.Subtest(test=perftest, name="Large RDMA Send", number='6',arg='ib_send_bw '+large_test))

IBPerftest = test.Test(tests=subtests, description="Tests core RDMA operations across a network, validates operation of endpoints at the RDMA level.")


def stress_test():
    streamctl.stdout.on()
    i = input("Select two ports such that it has to cross both switches.")
    print("Received: {}".format(i))
    streamctl.stdout.off()
    return [False, "sample test"]

subtest=(subtest.Subtest(test=stress_test, name="Switch Load In ", number='1'))
IBStresstest= test.Test(tests=[subtest], description="Tests core RDMA operations across a network, validates operation of endpoints at the RDMA level.")
