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

def medi_run(env, name, out_pipe, in_pipe):
    while True:
        #TODO 받는거 QUEUE에 넣고 QUEUEING DELAY 적용해야함 (CONGESTION 이겠쥬?)
        cwnd = 1
        yield env.timeout(random.randint(1,5))
        received = yield in_pipe.get()
        #print("meid!!"+str(received))
        if received["target"] == "node" and received["des"] == name :
            #print(received)

            print(str(env.now) + " intermediate node " + str(name) +" received packet")
            Send(name,received,out_pipe)


def source_run(env, name, out_pipe, in_pipe):
    count = 0
    ack_count = 0
    check = 5
    while True:
        # TODO TCP 큐빅 부분 구현
        cwnd = 1
        yield env.timeout(0.1)
        if check != 0:
            for i in range(0, cwnd):
                packet = MakePacket(name, cwnd, i)
                Send(name,packet,out_pipe)
                print(str(env.now) + " node " + str(name) +" sent packet")
                count = count + 1
                print("source : "+ str(count))
                check = check -1

        received = yield in_pipe.get()
        #print(received)
        if received["target"] == "node" and received["des"] == name :
            print(str(env.now) + " node " + str(name) +" received packet!!!!!!!!!!!!!")
            if received["route"][-1] == name:
                print("ack received")
                ack_count += 1
                print(ack_count)
                # TODO 이거 ack파트인데, ack 받았을때 보낸거랑 매칭하기
                # TODO 보낸거 리스트에 쌓아두는것도 해야함. Queue구현해야할듯
            #print(packet)

# def oac_source_run(env, name, pipe, out_pipe , in_pipe):
def des_run(env, name, out_pipe, in_pipe):
    count = 0
    temp = None

    while True:
        #cwnd = 1
        #yield env.timeout(random.randint(6, 8))
        #for i in range(0, cwnd):
        #    packet = MakePacket(name, cwnd, i)
        #    Send(name,packet,out_pipe)
        received = yield in_pipe.get()

        if received["target"] == "node" and received["des"] == name :
            #print(received)
            temp = received
            print(str(env.now) + " destination node " + str(name) +" received packet")
            if received["route"][-1] != name:
                #Send(name,received,out_pipe)
                print("")
            else:
                count = count+0.5
                print("finally received ")
                if count == int(count):
                    print("destination : " + str(int(count)))
                    packet = MakePacket(name, received["cwnd"], received["cnt"],True)

                    Send(name, packet, out_pipe)
                    print("sent ack")

                received = None
                # TODO 만약 예상하는 다음 패킷이 안왔을 경우 중복 ACK 보내기
            #print(packet)

def link_run(env, name, out_pipe, in_pipe):
    while True:
        #TODO CHANNEL 모델, 지연, 손실.. 등등 구현하기
        packet = yield in_pipe.get()
        if packet['target'] == "link" and set([packet['start'], packet['des']]) == set(name):
            print(packet['route'])
            print(str(env.now) + " link " + str(name) +" received packet")
            Send(name, packet, out_pipe)
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
    route = routing(start,ack)
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
    else:
        #print(route)
        packet["size"] = m_packetsize
        packet["route"] = route
        packet["cnt"] = cnt
        packet["cwnd"] = cwnd
        packet["source"] = start
        packet["start"] = start
        packet["des"] = route[route.index(start) + 1]
        packet["target"] = "link"
        packet["ack"] = ack

    return packet

    # SendToLink(start, route[route.index(start) + 1], packet)
def Send(name,packet,out_pipe):
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

    env.process(source_run(env,sources[0],bc_pipe,bc_pipe.get_output_conn()))
    #for s in sources:
        #env.process(source_run(env, s, bc_pipe, bc_pipe.get_output_conn()))
        #TODO add agent
    # env.process(oac_source_run(env, agent,bc_pipe,bc_pipe.get_output_conn()))
    for l in link:
        env.process(link_run(env, l, bc_pipe, bc_pipe.get_output_conn()))
    for medi in intermediate:
        env.process(medi_run(env, medi, bc_pipe, bc_pipe.get_output_conn()))
    for des in destination:
        env.process(des_run(env, des, bc_pipe, bc_pipe.get_output_conn()))

    env.run(until=m_simtime)


main()
