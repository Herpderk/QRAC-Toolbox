#!/usr/bin/python3

from qrac.dynamics import Crazyflie
from qrac.trajectory import Circle
from qrac.control.acados_mpc import AcadosMpc
from qrac.sim.acados_plant import AcadosPlant
from qrac.sim.minimal_sim import MinimalSim
import numpy as np


def main():
    # get dynamics model
    model = Crazyflie(Ax=0, Ay=0, Az=0)

    # initialize controller
    Q = np.diag([40,40,40, 1,1,1, 20,20,20, 1,1,1])
    R = np.diag([0, 0, 0, 0])
    max_thrust = 0.64           # N
    u_max = max_thrust * np.ones(4)
    u_min = np.zeros(4)
    mpc_T = 0.01
    num_nodes = 32
    rt = False
    mpc = AcadosMpc(
        model=model, Q=Q, R=R, u_max=u_max, u_min=u_min, \
        time_step=mpc_T, num_nodes=num_nodes, real_time=rt,)

    # initialize simulator plant
    sim_T = mpc_T / 10
    plant = AcadosPlant(
        model=model, sim_step=sim_T, control_step=mpc_T)

    # initialize simulator and bounds
    lb_pose = [-10, -10, 0]
    ub_pose = [10, 10, 10]
    sim = MinimalSim(
        plant=plant, controller=mpc,
        lb_pose=lb_pose, ub_pose=ub_pose,)

    # define a circular trajectory
    traj = Circle(v=4, r=4, alt=4)

    # Run the sim for N control loops
    x0 = np.array([4,0,0, 0,0,0, 0,0,0, 0,0,0])
    N = int(round(30 / mpc_T))      # 30 seconds worth of control loops
    sim.start(x0=x0, max_steps=N, verbose=True)

    # track the given trajectory
    x_set = np.zeros(mpc.n_set)
    nx = model.nx
    dt = mpc.dt
    t0 = sim.timestamp
    while sim.is_alive:
        t = sim.timestamp
        for k in range(num_nodes):
            x_set[k*nx : k*nx + nx] = \
                np.array(traj.get_setpoint(t - t0))
            t += dt
        sim.update_setpoint(x_set=x_set)


if __name__=="__main__":
    main()