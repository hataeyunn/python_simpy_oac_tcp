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


def cubic_cwnd(wmax, T):
    scailing = 0.4
    decrease_factor = 0.7

    K = ((wmax * (1 - decrease_factor)) / scailing) ** (1.0 / 3.0)

    new_cwnd = scailing * ((T - K) ** (1.0 / 3.0)) + wmax

    return new_cwnd


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


def medi_run(env, name, out_pipe, in_pipe):
    while True:
        # TODO 받는거 QUEUE에 넣고 QUEUEING DELAY 적용해야함 (CONGESTION 이겠쥬?)
        yield env.timeout(random.randint(1, 5))
        received = yield in_pipe.get()
        # print("meid!!"+str(received))
        if received["target"] == "node" and received["des"] == name:
            # print(received)

            # print(str(env.now) + " intermediate node " + str(name) +" received packet")
            Send(name, received, out_pipe)


def source_run(env, name, out_pipe, in_pipe):
    #TODO 프로세스단위로 바꿈
    file_size = 5120000
    total_num_cwnd = file_size / m_packetsize
    sent = []
    complete = []
    cwnd = 5
    num_resend = 0
    avail_send = 1
    sent_RTT = 0
    duplicate = 0
    last_ack = [1, 1]
    sent_count = 0
    while True:
        # TODO TCP 큐빅 부분 구현
        yield env.timeout(0.1)
        if avail_send:
            for i in range(0, cwnd-num_resend):
                packet = MakePacket(name, cwnd, i + 1)
                sent.append([cwnd, i + 1])
                Send(name, packet, out_pipe)
                print(str(env.now) + " node " + str(name) +" sent packet")
                # print("source : "+ str(count))
                if i == cwnd-1:
                    last_sent_RTT = env.now
                    avail_send = 0

            num_resend = 0

        received = yield in_pipe.get()
        # print(received)
        if received["target"] == "node" and received["des"] == name:
            # print(str(env.now) + " node " + str(name) +" received Ack packet")
            if received["route"][-1] == name:
                if received["resend"] == False:
                    print("source receive : " +str([received["cwnd"], received["cnt"]]))
                    try:
                        sent.remove([received["cwnd"],received["cnt"]])
                        print(sent)
                    except ValueError:
                        print("")
                    sent_count += 1
                else :
                    print("resend success " + str([received["cwnd"], received["cnt"]]))
                    print(sent)

                    packet = MakePacket(name, received["cwnd"],received["cnt"],False,True)
                    Send(name, packet, out_pipe)
                    num_resend += 1


# def oac_source_run(env, name, pipe, out_pipe , in_pipe):
def des_run(env, name, out_pipe, in_pipe):
    count = 0
    temp = None
    expected = [0, 1]
    wait_list = []
    received_list = []
    while True:
        # cwnd = 1
        # yield env.timeout(random.randint(6, 8))
        # for i in range(0, cwnd):
        #    packet = MakePacket(name, cwnd, i)
        #    Send(name,packet,out_pipe)
        received = yield in_pipe.get()
        if received["target"] == "node" and received["des"] == name:
            if received not in received_list:
                # print(received)
                temp = received
                # print(str(env.now) + " destination node " + str(name) +" received packet")
                if received["route"][-1] == name:
                    print("des receive " + str([received["cwnd"], received["cnt"]]))
                    print("expected " + str([expected[0], expected[1]]))

                    # Send(name,received,out_pipe)
                    if (expected == [received["cwnd"], received["cnt"]] or (expected == [0,1])and received["cnt"] == 1) :
                        print("correct expect : " + str([expected[0],expected[1]]))
                        received_list.append(received)
                        packet = MakePacket(name, received["cwnd"], received["cnt"],True)
                        Send(name, packet, out_pipe)
                        if expected[0]!= expected[1]:
                            expected = [received["cwnd"],expected[1]+1]
                        else :
                            expected = [0,1]


                    else :
                        print("error expect : " + str([expected[0],expected[1]]))
                        try:
                            wait_list.remove([received["cwnd"],received["cnt"]])
                            packet = MakePacket(name, expected[0], expected[1], True, False)
                            Send(name, packet, out_pipe)
                        except ValueError:
                            if expected !=[0,1]:
                                packet = MakePacket(name, expected[0],expected[1], True,True)
                                Send(name, packet, out_pipe)

                            packet = MakePacket(name, received["cwnd"], received["cnt"], True, False)
                            Send(name, packet, out_pipe)
                            wait_list.append([expected[0],expected[1]])
                            if expected != [0,1]:
                                if received["resend"] != True and received["cwnd"] != received["cnt"]:
                                    expected = [expected[0],expected[1]+1]
                                elif received["resend"] != True and received["cwnd"] == received["cnt"]:
                                    expected = [0,1]

                # print(packet)


def link_run(env, name, out_pipe, in_pipe):
    while True:
        # TODO CHANNEL 모델, 지연, 손실.. 등등 구현하기
        packet = yield in_pipe.get()
        if packet['target'] == "link" and set([packet['start'], packet['des']]) == set(name):
            # print(str(env.now) + " link " + str(name) +" received packet")
            Send(name, packet, out_pipe)
            # print(packet)


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


def MakePacket(start, cwnd, cnt, ack=False, resend = False):
    route = routing(start, ack)
    packet = OrderedDict()
    if not ack:
        packet["size"] = m_packetsize
        packet["route"] = route
        packet["cnt"] = cnt
        packet["cwnd"] = cwnd
        packet["source"] = start
        packet["start"] = start
        packet["des"] = route[route.index(start) + 1]
        packet["target"] = "link"
        packet["ack"] = ack
        packet["resend"] = resend
    else:
        # print(route)
        packet["size"] = m_packetsize
        packet["route"] = route
        packet["cnt"] = cnt
        packet["cwnd"] = cwnd
        packet["source"] = start
        packet["start"] = start
        packet["des"] = route[route.index(start) + 1]
        packet["target"] = "link"
        packet["ack"] = ack
        packet["resend"] = resend


    return packet

    # SendToLink(start, route[route.index(start) + 1], packet)


def Send(name, packet, out_pipe):
    if packet["target"] == "node":
        packet["start"] = name
        packet["des"] = packet["route"][packet["route"].index(name) + 1]
    if name in sources or name in destination or name in intermediate:
        packet["target"] = "link"
    else:
        packet["target"] = "node"

    out_pipe.put(packet)


def SendToLink(start, des, packet):
    packet["hop"] = des
    packet["target"] = 'link'

    # should add delay in this line


def main():
    env = simpy.Environment()
    bc_pipe = BroadcastPipe(env)

    env.process(source_run(env, sources[0], bc_pipe, bc_pipe.get_output_conn()))
    # for s in sources:
    # env.process(source_run(env, s, bc_pipe, bc_pipe.get_output_conn()))
    # TODO add agent
    # env.process(oac_source_run(env, agent,bc_pipe,bc_pipe.get_output_conn()))
    for l in link:
        env.process(link_run(env, l, bc_pipe, bc_pipe.get_output_conn()))
    for medi in intermediate:
        env.process(medi_run(env, medi, bc_pipe, bc_pipe.get_output_conn()))
    for des in destination:
        env.process(des_run(env, des, bc_pipe, bc_pipe.get_output_conn()))

    env.run(until=m_simtime)


main()
