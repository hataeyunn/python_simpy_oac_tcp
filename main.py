import simpy
import json
from collections import OrderedDict
import random

m_access_delay = 30
m_bottleneck_delay = 30
m_packetsize = 1024  # byte
m_simtime = 50000

sources = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
destination = ["10.0.0.6", "10.0.0.7", "10.0.0.8"]
intermediate = ["10.0.0.4", "10.0.0.5"]
agent = "10.0.0.3"
link = [tuple([sources[0], intermediate[0]]), tuple([sources[1], intermediate[0]]), tuple([agent, intermediate[0]]),
        tuple([intermediate[0], intermediate[1]]), tuple([intermediate[1], destination[0]]),
        tuple([intermediate[1], destination[1]]), tuple([intermediate[1], destination[2]])]

delay = {link[0]: m_access_delay, link[1]: m_access_delay, link[2]: m_access_delay, link[3]: m_bottleneck_delay,
         link[4]: m_access_delay, link[5]: m_access_delay, link[6]: m_access_delay}  # sec


class BroadcastPipe(object):
    """A Broadcast pipe that allows one process to send messages to many.

    This construct is useful when message consumers are running at
    different rates than message generators and provides an event
    buffering to the consuming processes.

    The parameters are used to create a new
    :class:`~simpy.resources.store.Store` instance each time
    :meth:`get_output_conn()` is called.

    """

    def __init__(self, env, capacity=simpy.core.Infinity):
        self.env = env
        self.capacity = capacity
        self.pipes = []

    def put(self, value):
        """Broadcast a *value* to all receivers."""
        if not self.pipes:
            raise RuntimeError('There are no output pipes.')
        events = [store.put(value) for store in self.pipes]
        return self.env.all_of(events)  # Condition event for all "events"

    def get_output_conn(self):
        """Get a new output connection for this broadcast pipe.

        The return value is a :class:`~simpy.resources.store.Store`.

        """
        pipe = simpy.Store(self.env, capacity=self.capacity)
        self.pipes.append(pipe)
        return pipe


def source_run(env, name, out_pipe, in_pipe):
    cwnd = 5
    yield env.timeout(random.randint(6, 10))
    for i in range(0, cwnd):
        packet = MakePacket(name, cwnd, i)
        out_pipe.put(packet)


# def oac_source_run(env, name, pipe, out_pipe , in_pipe):


def link_run(env, name, out_pipe, in_pipe):
    while True:
        packet = yield in_pipe.get()
        if packet['target'] == "link" and set([packet['start'], packet['des']]) == set(name):
            print(str(env.now) + " link " + str(name) +" received packet")
            #print(packet)


def routing(A, ack=False):
    route = []
    if not ack:
        route.append(A)
        route.append(intermediate[0])
        route.append(intermediate[1])
        route.append(destination[sources.index(A)])
    else:
        route.append(A)
        route.append(intermediate[1])
        route.append(intermediate[0])
        route.append(sources[destination.index(A)])

    return route


def MakePacket(start, cwnd, cnt, ack=False):
    route = routing(start)
    packet = OrderedDict()
    if not ack:
        packet["size"] = m_packetsize
        packet["route"] = route
        packet["cnt"] = cnt
        packet["num"] = cwnd
        packet["source"] = start
        packet["start"] = start
        packet["des"] = route[route.index(start) + 1]
        packet["target"] = "link"
    else:
        packet["cnt"] = cnt
        packet["source"] = start
        packet["target"] = "link"
        packet["start"] = start
        packet["des"] = route[route.index(start) + 1]

    return packet

    # SendToLink(start, route[route.index(start) + 1], packet)


def SendToLink(start, des, packet):
    packet["hop"] = des
    packet["target"] = 'link'

    # should add delay in this line


def main():
    env = simpy.Environment()
    bc_pipe = BroadcastPipe(env)

    for s in sources:
        env.process(source_run(env, s, bc_pipe, bc_pipe.get_output_conn()))
    # env.process(oac_source_run(env, agent,bc_pipe,bc_pipe.get_output_conn()))
    for l in link:
        env.process(link_run(env, l, bc_pipe, bc_pipe.get_output_conn()))

    env.run(until=m_simtime)


main()
