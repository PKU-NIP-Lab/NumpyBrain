import time

import matplotlib.pyplot as plt
import numpy as np

import npbrain as nn

nn.profile.set_backend('numba')

dt = 0.05
nn.profile.set_dt(dt)
np.random.seed(12345)

# Parameters
num_exc = 3200
num_inh = 800
taum = 20
taue = 5
taui = 10
Vt = -50
Vr = -60
El = -60
Erev_exc = 0.
Erev_inh = -80.
I = 20.
we = 0.6  # excitatory synaptic weight (voltage)
wi = 6.7  # inhibitory synaptic weight


def COBA(geometry, ref=5.0, name='COBA'):
    var2index = dict(V=0, ge=1, gi=2)
    num, geometry = nn.format_geometry(geometry)

    state = nn.initial_neu_state(3, num)
    state[0] = np.random.randn(num) * 5. - 55.

    def update_state(neu_state, t):
        not_in_ref = (t - neu_state[-2]) > ref
        neu_state[-5] = not_in_ref
        not_ref_idx = np.where(not_in_ref)[0]
        for idx in not_ref_idx:
            v = neu_state[0, idx]
            ge = neu_state[1, idx]
            gi = neu_state[2, idx]
            ge -= ge / taue * dt
            gi -= gi / taui * dt
            v += (ge * (Erev_exc - v) + gi * (Erev_inh - v) - (v - El) + I) / taum * dt
            neu_state[0, idx] = v
            neu_state[1, idx] = ge
            neu_state[2, idx] = gi
        # judge spike
        spike_idx = nn.judge_spike(neu_state, Vt, t)
        for idx in spike_idx:
            neu_state[0, idx] = Vr
            neu_state[-5, idx] = 0.

    return nn.Neurons(**locals())


exc_pre, exc_post, exc_acs = nn.connect.fixed_prob(
    num_exc, num_exc + num_inh, 0.02, include_self=False)
exc_anchors = np.zeros((2, num_exc + num_inh), dtype=np.int32)
exc_anchors[:, :num_exc] = exc_acs

inh_pre, inh_post, inh_anchors = nn.connect.fixed_prob(
    list(range(num_exc, num_exc + num_inh)),
    num_exc + num_inh, 0.02, include_self=False)


def Synapse(pre, post, delay=None, name='nromal_synapse'):
    var2index = dict()
    num_pre = pre.num
    num_post = post.num

    num = len(exc_pre)
    state = nn.initial_syn_state(delay, num_pre, num_post * 2, num)

    @nn.syn_delay
    def update_state(syn_state, t):
        spike = syn_state[0][-1]
        spike_idx = np.where(spike > 0.)[0]
        # get post-synaptic values
        g = np.zeros(num_post * 2)
        g2 = np.zeros(num_post)
        for i_ in spike_idx:
            if i_ < num_exc:
                idx = exc_anchors[:, i_]
                exc_post_idx = exc_post[idx[0]: idx[1]]
                g[exc_post_idx] += we
            else:
                idx = inh_anchors[:, i_]
                inh_post_idx = inh_post[idx[0]: idx[1]]
                g2[inh_post_idx] += wi
        g[num_post:] = g2
        return g

    def output_synapse(syn_state, index2var, post_neu_state):
        output_idx = index2var[-2]
        syn_val = syn_state[output_idx[0]][output_idx[1]]
        ge = syn_val[:num_post]
        gi = syn_val[num_post:]
        for idx in range(num_post):
            post_neu_state[1, idx] += ge[idx] * post_neu_state[-5, idx]
            post_neu_state[2, idx] += gi[idx] * post_neu_state[-5, idx]

    return nn.Synapses(**locals())


neurons = COBA(num_exc + num_inh)
syn = Synapse(neurons, neurons)
mon = nn.StateMonitor(neurons, ['spike'])
net = nn.Network(syn=syn, neu=neurons, mon=mon)

t0 = time.time()
net.run(5 * 1000., report=True)
print('Used time {} s.'.format(time.time() - t0))

index, time = nn.raster_plot(mon, net.run_time())
plt.plot(time, index, ',k')
plt.xlabel('Time (ms)')
plt.ylabel('Neuron index')
plt.show()
