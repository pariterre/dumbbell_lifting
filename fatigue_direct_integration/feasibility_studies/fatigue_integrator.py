import os
from typing import Any

import numpy as np
from matplotlib import pyplot as plt
from time import perf_counter
from scipy import integrate

from .enums import Integrator
from .study_configuration import StudyConfiguration
from .fatigue_model import FatigueModel


class Result:
    def __init__(self, t, y):
        self.t = t
        self.y = y


class FatigueIntegrator:
    def __init__(self, study_configuration: StudyConfiguration):
        self.study = study_configuration
        self._has_run: bool = False
        self._results: list[list[Result, ...], ...] = []
        self._performing_time: list[list[float, ...], ...] = []
        self.axes = None

    @property
    def results(self):
        if not self._has_run:
            raise RuntimeError("run() must be called before getting the results")
        return self._results

    def perform(self):
        """
        Perform the integration for all the fatigue_models
        repeat: int
            The number of time to perform the analysis
        """

        t_eval = self.study.t
        for _ in range(self.study.repeat):
            self._results.append([])
            self._performing_time.append([])
            for fatigue in self.study.fatigue_models:
                starting_time = perf_counter()
                if fatigue.integrator == Integrator.RK45:
                    out = self.rk45(t_eval, fatigue)
                elif fatigue.integrator == Integrator.RK4:
                    out = self.rk4(t_eval, fatigue)
                else:
                    raise ValueError("Wrong selection of integrator")
                self._performing_time[-1].append(perf_counter() - starting_time)

                self._results[-1].append(out)

        self._has_run = True

    def rk45(self, t_eval, fatigue) -> Result:
        t_span = (self.study.t[0], self.study.t[-1])
        x0 = fatigue.initial_guess
        out: Any = integrate.solve_ivp(lambda t, x: self._dynamics(t, x, fatigue), t_span, x0, t_eval=t_eval)
        return Result(out.t, out.y)

    def rk4(self, t_eval, fatigue) -> Result:
        def next_step(t0, x):
            k1 = self._dynamics(t0, x, fatigue)
            k2 = self._dynamics(t0 + h / 2, x + h / 2 * k1, fatigue)
            k3 = self._dynamics(t0 + h / 2, x + h / 2 * k2, fatigue)
            k4 = self._dynamics(t0 + h, x + h * k3, fatigue)
            return x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)

        h = self.study.t[1] - self.study.t[0]
        y = np.ndarray((3, self.study.t.shape[0]))
        x0 = fatigue.initial_guess
        for i, t in enumerate(t_eval):
            y[:, i] = next_step(t, x0)
            x0 = y[:, i]
        return Result(t_eval, y)

    def plot_results(self, font_size: int = 20, maximized: bool = False):
        fig = plt.figure()
        fig.set_size_inches(16, 9)
        # plt.rcParams["text.usetex"] = True
        plt.rcParams["text.latex.preamble"] = (r"\usepackage{siunitx}",)
        plt.rcParams["font.family"] = "Times New Roman"
        self.axes = plt.axes()

        if not self._has_run:
            raise RuntimeError("run() must be called before plotting the results")

        if self.study.plot_options is None:
            return

        for model, result, plot_options in zip(
            self.study.fatigue_models, self._results[-1], self.study.plot_options.options
        ):
            self._add_result_to_plot(model, result, plot_options)
        plt.plot(
            self.study.t,
            [self.study.target_function.function(t) * 100 for t in self.study.t],
            color="tab:blue",
            linewidth=4,
        )

        self.axes.set_title(self.study.plot_options.title, fontsize=1.5 * font_size)
        self.axes.set_xlabel(r"Time (\SI{}{\second})", fontsize=font_size)
        self.axes.set_ylabel(r"Level (\SI{}{\percent})", fontsize=font_size)
        self.axes.set_xlim(self.study.plot_options.xlim)
        self.axes.set_ylim(self.study.plot_options.ylim)
        if not self.study.plot_options.keep_frame:
            self.axes.spines["top"].set_visible(False)
            self.axes.spines["right"].set_visible(False)
        self.axes.tick_params(axis="both", labelsize=font_size)
        if self.study.plot_options.legend is not None:
            supplementary_legend = None
            if self.study.plot_options.supplementary_legend:
                supplementary_legend = plt.legend(
                    self.axes.get_lines(),
                    self.study.plot_options.supplementary_legend,
                    loc="lower right",
                    fontsize=font_size,
                    framealpha=0.9,
                    title=self.study.plot_options.supplementary_legend_title,
                    title_fontsize=20,
                )
            self.axes.legend(
                self.study.plot_options.legend,
                loc="upper right" if supplementary_legend is not None else "lower right",
                fontsize=font_size,
                framealpha=0.9,
                title=self.study.plot_options.legend_title,
                title_fontsize=20,
            )
            if supplementary_legend is not None:
                self.axes.add_artist(supplementary_legend)

        if maximized:
            plt.get_current_fig_manager().window.showMaximized()

        if self.study.plot_options.save_name:
            plt.savefig(f"{self.prepare_and_get_results_dir()}/{self.study.plot_options.save_name}.png", dpi=100)
            plt.savefig(f"{self.prepare_and_get_results_dir()}/{self.study.plot_options.save_name}.pdf", format="pdf")
            plt.savefig(f"{self.prepare_and_get_results_dir()}/{self.study.plot_options.save_name}.eps", format="eps")

        plt.show()

    def print_integration_time(self):
        if not self._has_run:
            raise RuntimeError("run() must be called before printing the results")

        print(f"Individual integration time:")
        time = np.array(self._performing_time).T
        for model, t in zip(self.study.fatigue_models, time):
            print(
                f"\t{type(model).__name__}: {np.mean(t) / self.study.t[-1]:1.3f} seconds "
                f"per integrated second for {np.mean(t):1.3f} second total (mean of {t.shape[0]} trials)"
            )

    def print_rmse(self):
        if not self._has_run:
            raise RuntimeError("run() must be called before printing the results")

        if len(self.study.fatigue_models) != 2:
            raise RuntimeError("rmse must have exactly 2 models to be called")

        if sum([False if m.rms_indices is None else True for m in self.study.fatigue_models]) != 2:
            raise ValueError("rms_indices were not all provided in the study configuration")

        # Get aliases
        models = self.study.fatigue_models

        e = self._results[-1][0].y[models[0].rms_indices, :] - self._results[-1][1].y[models[1].rms_indices, :]
        se = e**2
        mse = np.sum(se, axis=1) / self.study.n_points
        rmse = np.sqrt(mse)

        table = f"The RMSE between {type(models[0]).__name__} and {type(models[1]).__name__} is {rmse}"

        save_path = f"{self.prepare_and_get_results_dir()}/rmse.txt"
        with open(save_path, "w", encoding="utf8") as file:
            file.write(table)
        print("RMSE written in the results folder")

    def print_custom_analyses(self):
        if not self._has_run:
            raise RuntimeError("run() must be called before printing the results")

        table = ""
        for model, results in zip(self.study.fatigue_models, self._results[-1]):
            if model.custom_analyses is None:
                continue
            for custom_analysis in model.custom_analyses:
                table += f"{custom_analysis.name} for {type(model).__name__}: {custom_analysis.fun(results)}\n"

        if self.study.common_custom_analyses is not None:
            for custom_analysis in self.study.common_custom_analyses:
                table += f"{custom_analysis.name} \n"
                for model, results in zip(self.study.fatigue_models, self._results[-1]):
                    table += f"\tfor {model.table_name}: {custom_analysis.fun(results)}\n"

        save_path = f"{self.prepare_and_get_results_dir()}/custom_analysis.txt"
        with open(save_path, "w", encoding="utf8") as file:
            file.write(table)
        print("Custom analyses written in the results folder")

    def prepare_and_get_results_dir(self):
        try:
            os.mkdir("results")
        except FileExistsError:
            pass

        try:
            os.mkdir(f"results/{self.study.name}")
        except FileExistsError:
            pass
        return f"results/{self.study.name}"

    def _dynamics(self, t, x, fatigue):
        return fatigue.apply_dynamics(self.study.target_function.function(t) / fatigue.scaling, x)

    @staticmethod
    def _add_result_to_plot(model: FatigueModel, results: Result, plot_options: Any):
        plt.stackplot(results.t, results.y * 100, colors=model.colors, alpha=0.4)
        if model.print_sum:
            if "color" not in plot_options:
                plot_options["color"] = "black"
            plt.plot(results.t, np.sum(results.y * 100, axis=0), **plot_options)
