#!/usr/bin/python3

import multiprocessing as mp
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import time
from typing import Tuple


class MinimalSim():
    def __init__(
        self,
        backend,
        controller,
        lb_pose: np.ndarray,
        ub_pose: np.ndarray,
        data_len=400,
        sprite_size=1.0,
    ) -> None:
        self._assert(
            backend, controller, lb_pose, ub_pose, data_len, sprite_size)
        self._backend = backend
        self._controller = controller
        self._xlim = (lb_pose[0], ub_pose[0])
        self._ylim = (lb_pose[1], ub_pose[1])
        self._zlim = (lb_pose[2], ub_pose[2])
        self._data_len = data_len
        self._p1 = np.array([sprite_size / 2, 0, 0, 1])
        self._p2 = np.array([-sprite_size / 2, 0, 0, 1])
        self._p3 = np.array([0, sprite_size / 2, 0, 1])
        self._p4 = np.array([0, -sprite_size / 2, 0, 1])

        self._fig, self._ax = self._init_fig()
        self._run_flag = mp.Value("b", False)


    @property
    def is_alive(self) -> bool:
        return self._run_flag.value


    def start(
        self,
        x0: np.ndarray,
        max_steps=-1,
    ) -> None:
        if self._run_flag.value:
            raise RuntimeError(
                "You cannot start the sim when it is already running. Wait for 'is_alive' to be False to start the sim again.")
        else:
            assert len(x0) == self._backend.nx
            assert type(max_steps) == int
            self._init_vars(x0, max_steps)
            print("Starting simulator...")
            manager_proc = mp.Process(target=self._run_procs, args=[])
            manager_proc.start()


    def stop(self) -> None:
        self._run_flag.value = False


    def update_setpoint(
        self,
        x_set: np.ndarray,
    ) -> None:
        assert len(x_set) == self._backend.nx
        try:
            self._x_set[:] = x_set
        except AttributeError:
            raise RuntimeError(
                "You cannot assign a setpoint before the sim starts.")


    def _init_vars(
        self,
        x0: np.ndarray,
        max_steps: int
    ) -> None:
        self._pose_data = np.empty((self._data_len, 3))
        self._data_ind = 0
        self._x = mp.Array("f", x0)
        self._x_set = mp.Array("f", x0)
        self._max_steps = mp.Value("i", max_steps)
        self._steps = mp.Value("i", 0)
        self._sim_time = mp.Value("f", 0.0)
        self._run_flag.value = True


    def _run_procs(self) -> None:
        frontend_proc = mp.Process(target=self._run_frontend, args=[])
        backend_proc = mp.Process(target=self._run_backend, args=[])
        frontend_proc.start()
        backend_proc.start()
        backend_proc.join()
        frontend_proc.join()
        print("\nSimulator successfully exited.")
        #self._frontend_proc.start()
        #self._backend_proc.start()
        #if self._max_steps.value > 0:
        #    self._join_procs()


    def _run_frontend(self) -> None:
        plt.ion()
        while self._run_flag.value:
            self._plot(self._x[:], timer=True)
        plt.cla()
        plt.ioff()
        #plt.close()


    def _plot(
        self,
        x: np.ndarray,
        timer=False,
    ) -> None:
        st = time.perf_counter()
        self._update_data(x)
        p1, p2, p3, p4 = self._transform_quad(x)
        plt.cla()
        self._plot_quad(p1, p2, p3, p4)
        self._set_plot_settings()
        if timer: print(f"render runtime: {time.perf_counter() - st}")


    def _update_data(
        self,
        x: np.ndarray,
    ) -> None:
        curr_pose = x[:3]
        prev_pose = self._pose_data[self._data_ind-1]
        dist = np.linalg.norm(curr_pose-prev_pose)
        if dist < 0.1:
            pass
        else:
            self._pose_data[self._data_ind] = x[:3]
            if self._data_ind >= len(self._pose_data)-1:
                self._data_ind = 0
            else:
                self._data_ind += 1


    def _transform_quad(
            self,
            x: np.ndarray,
        ) -> Tuple[float]:
            T = self._get_transform(x)
            p1_t = T @ self._p1
            p2_t = T @ self._p2
            p3_t = T @ self._p3
            p4_t = T @ self._p4
            return p1_t, p2_t, p3_t, p4_t


    def _get_transform(
        self,
        x: np.ndarray,
    ) -> np.ndarray:
        Rx = np.array([
            [1,            0,             0],
            [0, np.cos(x[3]), -np.sin(x[3])],
            [0, np.sin(x[3]),  np.cos(x[3])],
        ])
        Ry = np.array([
            [ np.cos(x[4]),  0,  np.sin(x[4])],
            [            0,  1,             0],
            [-np.sin(x[4]),  0,  np.cos(x[4])],
        ])
        Rz = np.array([
            [np.cos(x[5]),    -np.sin(x[5]),    0],
            [np.sin(x[5]),     np.cos(x[5]),    0],
            [          0,               0,      1],
        ])
        R = Rz @ Ry @ Rx
        T = np.block([R, np.reshape(x[:3], (3,1))])
        return T


    def _plot_quad(
        self,
        p1: float,
        p2: float,
        p3: float,
        p4: float,
    ) -> None:
        self._ax.plot([p1[0], p2[0], p3[0], p4[0]],
                     [p1[1], p2[1], p3[1], p4[1]],
                     [p1[2], p2[2], p3[2], p4[2]], "k.", markersize=9)
        self._ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
                     [p1[2], p2[2]], "b-", linewidth=3)
        self._ax.plot([p3[0], p4[0]], [p3[1], p4[1]],
                     [p3[2], p4[2]], "b-", linewidth=3)
        self._ax.plot(self._pose_data[:,0], self._pose_data[:,1],
                     self._pose_data[:,2], "r.", markersize=1)
        timestamp = round(self._sim_time.value, 4)
        #plt.text(0.02, 0.5, timestamp, fontsize=14, transform=plt.gcf().transFigure)
        plt.gcf().text(0.02, 0.5, str(timestamp), fontsize=14)


    def _set_plot_settings(self) -> None:
        self._ax.set_xlim(self._xlim)
        self._ax.set_ylim(self._ylim)
        self._ax.set_zlim(self._zlim)
        self._ax.set_xticks(range(self._xlim[0], self._xlim[1], 2))
        self._ax.set_yticks(range(self._ylim[0], self._ylim[1], 2))
        self._ax.set_zticks(range(self._zlim[0], self._zlim[1]+2, 2))
        self._ax.xaxis.set_rotate_label(False)
        self._ax.set_xlabel(r"$\bf{x}$", fontsize=15)
        self._ax.yaxis.set_rotate_label(False)
        self._ax.set_ylabel(r"$\bf{y}$", fontsize=15)
        self._ax.zaxis.set_rotate_label(False)
        self._ax.set_zlabel(r"$\bf{z}$", fontsize=15,)
        plt.pause(0.00001)


    def _run_backend(self) -> None:
        while self._run_flag.value:
            x0 = np.array(self._x[:])
            x_set = np.array(self._x_set[:])
            u = self._controller.get_input(x0=x0, x_set=x_set, timer=True)
            x = self._backend.update(x0=x0, u=u, timer=True)
            self._x[:] = x
            print(f"u: {u}")
            print(f"x: {x}")
            self._update_time()


    def _update_time(self):
        self._steps.value += 1
        self._sim_time.value += self._controller.dt
        if self._max_steps.value > 0 and self._steps.value == self._max_steps.value:
            self._run_flag.value = False


    def _init_fig(self) -> Tuple[matplotlib.figure.Figure, plt.Axes]:
        fig = plt.figure(figsize=(9,10))
        fig.canvas.mpl_connect("key_release_event",
            lambda event: [exit(0) if event.key == "escape" else None])
        ax = fig.add_subplot(projection="3d")
        return fig, ax


    def _assert(
        self,
        backend,
        controller,
        lb_pose: np.ndarray,
        ub_pose: np.ndarray,
        data_len: int,
        sprite_size: float,
    ) -> None:
        try:
            backend.update
        except AttributeError:
            raise NotImplementedError(
                "Please implement an 'update' method in your backend class!")
        try:
            backend.nx
        except AttributeError:
            raise NotImplementedError(
                "Please implement an 'nx' variable in your backend class!")
        try:
            backend.nu
        except AttributeError:
            raise NotImplementedError(
                "Please implement an 'nu' variable in your backend class!")
        try:
            controller.get_input
        except AttributeError:
            raise NotImplementedError(
                "Please implement a 'get_input' method in your controller class!")
        try:
            controller.dt
        except AttributeError:
            raise NotImplementedError(
                "Please implement an 'dt' variable in your controller class!")

        if len(lb_pose) != 3:
            raise ValueError(
                "Please input a lower bound on position as a 3D vector!")
        if len(ub_pose) != 3:
            raise ValueError(
                "Please input an upper bound on position as a 3D vector!")
        if type(data_len) != int:
            raise ValueError(
                "Please input the desired data length as an integer!")
        if (type(sprite_size) != int and type(sprite_size) != float):
            raise ValueError(
                "Please input the desired sprite size as an integer or float!")