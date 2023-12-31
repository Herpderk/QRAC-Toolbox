#!/usr/bin/python3

import casadi as cs
import numpy as np
from typing import Tuple
from acados_template import AcadosModel


class Quadrotor():
    def __init__(
        self,
        m: float,
        Ixx: float,
        Iyy: float,
        Izz: float,
        Ax: float,
        Ay: float,
        Az: float,
        bx: np.ndarray,
        by: np.ndarray,
        k: np.ndarray,
        name="Nonlinear_Quadrotor",
    ) -> None:
        """
        Struct containing mass, moments of inertias, linear air resistance terms,
        distances of rotors from the body-frame x-axis, distances of rotors from the body-frame y-axis,
        and torque coefficient magnitudes associated with each rotor's thrust.
        """
        self._assert(m, Ixx, Iyy, Izz, Ax, Ay, Az, bx, by, k, name)
        self.m = m
        self.Ixx = Ixx
        self.Iyy = Iyy
        self.Izz = Izz
        self.Ax = Ax
        self.Ay = Ay
        self.Az = Az
        self.bx = bx
        self.by = by
        self.k = k
        self.name = name
        self._get_dynamics()
        self.nx = self.x.shape[0]
        self.nu = self.u.shape[0]


    def get_acados_model(self):
        model_ac = AcadosModel()
        model_ac.f_expl_expr = self.xdot
        model_ac.x = self.x
        model_ac.xdot = self.xdot
        model_ac.u = self.u
        model_ac.name = self.name
        return model_ac


    def _get_dynamics(self) -> None:
        # State Variables: position, rotation, velocity, and body-frame angular velocity
        x = cs.SX.sym("x")
        y = cs.SX.sym("y")
        z = cs.SX.sym("z")
        phi = cs.SX.sym("phi")     # roll
        theta = cs.SX.sym("theta") # pitch
        psi = cs.SX.sym("psi")     # yaw
        x_d = cs.SX.sym("x_d")     # time-derivatives
        y_d = cs.SX.sym("y_d")
        z_d = cs.SX.sym("z_d")
        phi_d_B = cs.SX.sym("phi_d_B")
        theta_d_B = cs.SX.sym("theta_d_B")
        psi_d_B = cs.SX.sym("psi_d_B")
        self.x = cs.SX(cs.vertcat(
            x, y, z, phi, theta, psi,\
            x_d, y_d, z_d, phi_d_B, theta_d_B, psi_d_B
        ))

        # transformation from inertial to body frame ang vel
        W = cs.SX(cs.vertcat(
            cs.horzcat(1, 0, -cs.sin(theta)),
            cs.horzcat(0, cs.cos(phi), cs.cos(theta)*cs.sin(phi)),
            cs.horzcat(0, -cs.sin(phi), cs.cos(theta)*cs.cos(phi)),
        ))

        # rotation matrix from body frame to inertial frame
        Rx = cs.SX(cs.vertcat(
            cs.horzcat(1,            0,            0),
            cs.horzcat(0,  cs.cos(phi), -cs.sin(phi)),
            cs.horzcat(0,  cs.sin(phi),  cs.cos(phi)),
        ))
        Ry = cs.SX(cs.vertcat(
            cs.horzcat( cs.cos(theta),  0,  cs.sin(theta)),
            cs.horzcat(             0,  1,              0),
            cs.horzcat(-cs.sin(theta),  0,  cs.cos(theta)),
        ))
        Rz = cs.SX(cs.vertcat(
            cs.horzcat(cs.cos(psi),    -cs.sin(psi),    0),
            cs.horzcat(cs.sin(psi),     cs.cos(psi),    0),
            cs.horzcat(          0,               0,    1),
        ))
        self.R = Rz @ Ry @ Rx

        # drag terms
        self.A = cs.SX(np.diag([self.Ax, self.Ay, self.Az]))

        # Diagonal of inertial matrix
        self.J = cs.SX(np.diag([self.Ixx, self.Iyy, self.Izz]))

        # control allocation matrix
        self.B = cs.SX(cs.vertcat(
            self.by.reshape(1, self.by.shape[0]),
            -self.bx.reshape(1, self.bx.shape[0]),
            cs.horzcat(-self.k[0], self.k[1], -self.k[2], self.k[3]),
        ))

        # gravity vector
        g = cs.SX(cs.vertcat(0, 0, -9.81))

        # thrust of motors 1 to 4
        self.u = cs.SX.sym("u", 4)
        T = cs.SX(cs.vertcat(
            0, 0, self.u[0]+self.u[1]+self.u[2]+self.u[3]))

        # continuous-time dynamics
        v = cs.SX(cs.vertcat(x_d, y_d, z_d))
        w_B = cs.SX(cs.vertcat(phi_d_B, theta_d_B, psi_d_B))
        self.xdot = cs.SX(cs.vertcat(
            v,
            cs.inv(W) @ w_B,
            (self.R@T - self.A@v)/self.m + g,
            cs.inv(self.J) @ (self.B@self.u - cs.cross(w_B, self.J@w_B))
        ))


    def _assert(
        self,
        m: float,
        Ixx: float,
        Iyy: float,
        Izz: float,
        Ax: float,
        Ay: float,
        Az: float,
        bx: np.ndarray,
        by: np.ndarray,
        k: np.ndarray,
        name: str,
    ) -> None:
        for arg in [m, Ixx, Iyy, Izz, Ax, Ay, Az]:
            if (type(arg) != int and type(arg) != float):
                raise TypeError(f"{arg} should be an int or float!")
        for arg in [bx, by, k]:
            if len(arg) != 4:
                raise ValueError(f"{arg} should be a float vector of length 4!")
        if type(name) != str:
            raise TypeError("The name should be a string!")


def Crazyflie(
    Ax: float,
    Ay: float,
    Az: float,
) -> Quadrotor:
    """
    crazyflie system identification:
    https://www.research-collection.ethz.ch/handle/20.500.11850/214143
    """
    m = 0.028
    Ixx = 3.144988 * 10**(-5)
    Iyy = 3.151127 * 10**(-5)
    Izz = 7.058874 * 10**(-5)
    bx = np.array(
        [0.0283, 0.0283, -0.0283, -0.0283])
    by = np.array(
        [0.0283, -0.0283, -0.0283, 0.0283])
    k = 0.005964552 * np.ones(4)
    crazyflie = Quadrotor(
        m, Ixx, Iyy, Izz, Ax, Ay, Az, bx, by, k)
    return crazyflie
