# -*- coding: utf-8 -*-

import inspect
from copy import deepcopy

from .base_objects import BaseEnsemble
from .base_objects import BaseType
from .base_objects import ModelUseError
from .base_objects import NeuState
from .base_objects import _NEU_GROUP
from .. import numpy as np
from .. import profile
from ..tools import DictPlus

__all__ = [
    'NeuType',
    'NeuGroup',
]

_NEU_GROUP_NO = 0


class NeuType(BaseType):
    """Abstract Neuron Type.

    It can be defined based on a group of neurons or a single neuron.
    """

    def __init__(self, name, requires, steps, vector_based=True, heter_params_replace=None):
        super(NeuType, self).__init__(requires=requires, steps=steps, name=name, vector_based=vector_based,
                                      heter_params_replace=heter_params_replace)

    def run(self, duration, monitors, vars_init=None):
        # times
        if isinstance(duration, (int, float)):
            start, end = 0, duration
        elif isinstance(duration, (tuple, list)):
            assert len(duration) == 2, 'Only support duration with the format of "(start, end)".'
            start, end = duration
        else:
            raise ValueError(f'Unknown duration type: {type(duration)}')
        dt = profile.get_dt()
        times = np.arange(start, end, dt)

        # monitors
        mon = DictPlus()
        for k in monitors:
            mon[k] = np.zeros(len(times))
        mon['ts'] = times

        # variables
        variables = deepcopy(self.variables)
        if vars_init is not None:
            assert isinstance(vars_init, dict)
            for k, v in vars_init.items():
                variables[k] = v

        # get update function
        update = self.steps[0]
        assert callable(update)

        # initialize corresponding state
        ST = NeuState(variables)(1)

        # get the running _code
        code_scope = {'update': update, 'monitor': mon, 'ST': ST,
                      'mon_keys': monitors, 'dt': dt, 'times': times}
        code_args = inspect.getfullargspec(update).args
        mapping = {'ST': 'ST', '_t_': 't', '_i_': 'i', '_dt_': 'dt'}
        code_arg2call = [mapping[arg] for arg in code_args]
        code_lines = [f'def run_func():']
        code_lines.append(f'  for i, t in enumerate(times):')
        code_lines.append(f'    update({", ".join(code_arg2call)})')
        code_lines.append(f'    for k in mon_keys:')
        if self.vector_based:
            code_lines.append(f'      monitor[k][i] = ST[k][0]')
        else:
            code_lines.append(f'      monitor[k][i] = ST[k]')

        # run the model
        codes = '\n'.join(code_lines)
        exec(compile(codes, '', 'exec'), code_scope)
        code_scope['run_func']()
        return mon


class NeuGroup(BaseEnsemble):
    """Neuron Group.

    Parameters
    ----------
    model : NeuType
        The instantiated neuron type model.
    geometry : int, tuple
        The neuron group geometry.
    pars_update : dict, None
        Parameters to update.
    monitors : list, tuple, None
        Variables to monitor.
    name : str, None
        The name of the neuron group.
    """

    def __init__(self, model, geometry, pars_update=None, monitors=None, name=None):
        # name
        # -----
        if name is None:
            global _NEU_GROUP_NO
            name = f'NeuGroup{_NEU_GROUP_NO}'
            _NEU_GROUP_NO += 1
        else:
            name = name

        # num and geometry
        # -----------------
        if isinstance(geometry, (int, float)):
            geometry = (1, int(geometry))
        elif isinstance(geometry, (tuple, list)):
            if len(geometry) == 1:
                height, width = 1, geometry[0]
            elif len(geometry) == 2:
                height, width = geometry[0], geometry[1]
            else:
                raise ValueError('Do not support 3+ dimensional networks.')
            geometry = (height, width)
        else:
            raise ValueError()
        num = int(np.prod(geometry))
        self.geometry = geometry

        # model
        # ------
        try:
            assert isinstance(model, NeuType)
        except AssertionError:
            raise ModelUseError(f'{NeuGroup.__name__} receives an instance of {NeuType.__name__}, '
                                f'not {type(model).__name__}.')

        # initialize
        # ----------
        super(NeuGroup, self).__init__(model=model,
                                       pars_update=pars_update,
                                       name=name, num=num,
                                       monitors=monitors, cls_type=_NEU_GROUP)

        # ST
        # --
        self.ST = self.requires['ST'].make_copy(num)

    @property
    def _keywords(self):
        return super(NeuGroup, self)._keywords + ['geometry', ]
