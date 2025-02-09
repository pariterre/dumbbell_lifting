from typing import Protocol
import os

from bioptim import Solution
import numpy as np
from matplotlib import pyplot as plt

from .study_configuration import StudyConfiguration
from .ocp import DataType


class Conditions(Protocol):
    name: str
    value: StudyConfiguration


class Study:
    def __init__(self, conditions: Conditions):
        self.name = conditions.name
        self._has_run: bool = False
        self._plots_are_prepared: bool = False
        self.conditions: StudyConfiguration = conditions.value
        self.solution: list[Solution, ...] = []

    def run(self):
        for condition in self.conditions.studies:
            self.solution.append(condition.perform())
        self._has_run = True

    def print_results(self):
        print("Number of iterations")
        for study, sol in zip(self.conditions.studies, self.solution):
            print(f"\t{study.name} = {sol.iterations}")

        print("Total time to optimize")
        for study, sol in zip(self.conditions.studies, self.solution):
            print(f"\t{study.name} = {sol.real_time_to_optimize:0.3f} second")

        print("Mean time per iteration to optimize")
        for study, sol in zip(self.conditions.studies, self.solution):
            print(f"\t{study.name} = {sol.real_time_to_optimize / sol.iterations:0.3f} second")

    def generate_latex_table(self):
        if not self._has_run:
            raise RuntimeError("run() must be called before generating the latex table")

        table = (
            f"\\documentclass{{article}}\n"
            f"\n"
            f"\\usepackage{{amsmath}}\n"
            f"\\usepackage{{amssymb}}\n"
            f"\\usepackage[table]{{xcolor}}\n"
            f"\\usepackage{{threeparttable}}\n"
            f"\\usepackage{{makecell}}\n"
            f"\\definecolor{{lightgray}}{{gray}}{{0.91}}\n"
            f"\n\n"
            f"% Aliases\n"
            f"\\newcommand{{\\rmse}}{{RMSE}}\n"
            f"\\newcommand{{\\ocp}}{{OCP}}\n"
            f"\\newcommand{{\\controls}}{{\\mathbf{{u}}}}\n"
            f"\\newcommand{{\\states}}{{\\mathbf{{x}}}}\n"
            f"\\newcommand{{\\statesDot}}{{\\mathbf{{\\dot{{x}}}}}}\n"
            f"\\newcommand{{\\q}}{{\\mathbf{{q}}}}\n"
            f"\\newcommand{{\\qdot}}{{\\mathbf{{\\dot{{q}}}}}}\n"
            f"\\newcommand{{\\qddot}}{{\\mathbf{{\\ddot{{q}}}}}}\n"
            f"\\newcommand{{\\f}}{{\\mathbf{{f}}}}\n"
            f"\\newcommand{{\\taupm}}{{\\tau^{{\\pm}}}}\n"
            f"\\newcommand{{\\tauns}}{{\\tau^{{\\times}}}}\n"
            f"\n"
            f"\\newcommand{{\\condition}}{{C/}}\n"
            f"\\newcommand{{\\noFatigue}}{{\\varnothing}}\n"
            f"\\newcommand{{\\qcc}}{{4\\textsubscript{{CC}}}}\n"
            f"\\newcommand{{\\pe}}{{P\\textsubscript{{E}}}}\n"
            f"\\newcommand{{\\condTau}}{{{{\\condition}}{{\\tau}}{{}}}}\n"
            f"\\newcommand{{\\condTauNf}}{{{{\\condition}}{{\\tau}}{{\\noFatigue}}}}\n"
            f"\\newcommand{{\\condTauQcc}}{{{{\\condition}}{{\\tau}}{{\\qcc}}}}\n"
            f"\\newcommand{{\\condTauPe}}{{{{\\condition}}{{\\tau}}{{\\pe}}}}\n"
            f"\\newcommand{{\\condTaupm}}{{{{\\condition}}{{\\taupm}}{{}}}}\n"
            f"\\newcommand{{\\condTaupmQcc}}{{{{\\condition}}{{\\taupm}}{{\\qcc}}}}\n"
            f"\\newcommand{{\\condTaupmPe}}{{{{\\condition}}{{\\taupm}}{{\\pe}}}}\n"
            f"\\newcommand{{\\condTauns}}{{{{\\condition}}{{\\tauns}}{{}}}}\n"
            f"\\newcommand{{\\condTaunsQcc}}{{{{\\condition}}{{\\tauns}}{{\\qcc}}}}\n"
            f"\\newcommand{{\\condTaunsPe}}{{{{\\condition}}{{\\tauns}}{{\\pe}}}}\n"
            f"\\newcommand{{\\condAlpha}}{{{{\\condition}}{{\\alpha}}{{}}}}\n"
            f"\\newcommand{{\\condAlphaNf}}{{{{\\condition}}{{\\alpha}}{{\\noFatigue}}}}\n"
            f"\\newcommand{{\\condAlphaQcc}}{{{{\\condition}}{{\\alpha}}{{\\qcc}}}}\n"
            f"\\newcommand{{\\condAlphaPe}}{{{{\\condition}}{{\\alpha}}{{\\pe}}}}\n"
            f"\n\n"
            f"\\begin{{document}}\n"
            f"\n"
            f"\\begin{{table}}[!ht]\n"
            f" \\rowcolors{{1}}{{}}{{lightgray}}\n"
            f" \\caption{{Comparaison des métriques d'efficacité et de comportement entre les modèles de fatigue "
            f"appliqués sur une dynamique musculaire ou articulaire lors de la résolution d'un \\ocp{{}}}}\n"
            f" \\label{{table:faisabilite}}\n"
            f" \\begin{{threeparttable}}\n"
            f"  \\begin{{tabular}}{{lccccc}}\n"
            f"   \\hline\n"
            f"   \\bfseries Condition & "
            f"\\bfseries\\makecell[c]{{Nombre de\\\\variables/\\\\contraintes}} & "
            f"\\bfseries\\makecell[c]{{Nombre\\\\d'itérations}} & "
            f"\\bfseries\\makecell[c]{{Temps\\\\de calcul\\\\(s)}} & "
            f"\\bfseries\\makecell[c]{{Temps moyen\\\\par itération\\\\(s/iteration)}} & "
            f"\\bfseries\\makecell[c]{{$\\sum\\text{{\\rmse{{}}}}$\\\\pour $\\q$\\\\(rad)}}\\\\ \n"
            f"   \\hline\n"
        )

        all_has_converged = True
        for study, sol, rmse_index in zip(self.conditions.studies, self.solution, self.conditions.rmse_index):
            rmse = np.sum(self._rmse(DataType.STATES, "q", rmse_index, sol))
            rmse_str = f"{rmse:0.3e}" if rmse != 0 else "---"
            if rmse_str.find("e") >= 0:
                rmse_str = rmse_str.replace("e", "$\\times 10^{{")
                rmse_str += "}}$"
                rmse_str = rmse_str.replace("+0", "")
                rmse_str = rmse_str.replace("-0", "-")
                rmse_str = rmse_str.replace("$\\times 10^{{0}}$", "")

            nlp = study.ocp.nlp[0]
            n_var = nlp.ns * nlp.controls.shape + (nlp.ns + 1) * nlp.states.shape
            n_constraints = nlp.ns * study.ocp.nlp[0].states.shape + sum([g.bounds.shape[0] for g in nlp.g])

            study_name = study.name
            if sol.iterations == study.solver.max_iter:
                study_name += "*"
                all_has_converged = False

            table += (
                f"   {study_name} "
                f"& {n_var}/{n_constraints} "
                f"& {sol.iterations} "
                f"& {sol.real_time_to_optimize:0.3f} "
                f"& {sol.real_time_to_optimize / sol.iterations:0.3f} "
                f"& {rmse_str} \\\\\n"
            )
        table += f"   \\hline\n" f"  \\end{{tabular}}\n"

        if not all_has_converged:
            table += f"  \\begin{{tablenotes}}\n"
            table += f"   \\item * Condition n'ayant pas convergé (maximum d'itérations atteint)\n"
            table += f"  \\end{{tablenotes}}\n"

        table += f" \\end{{threeparttable}}\n"
        table += f"\\end{{table}}\n\n"
        table += f"\\end{{document}}\n"

        save_path = f"{self.prepare_and_get_results_dir()}/results.tex"

        with open(save_path, "w", encoding="utf8") as file:
            file.write(table)
        print("\n\nTex file generated in the results folder")

    def save_solutions(self):
        for study, sol in zip(self.conditions.studies, self.solution):
            study.ocp.save(sol, file_path=f"{self.prepare_and_get_results_dir()}/{study.save_name}")
            study.ocp.save(sol, file_path=f"{self.prepare_and_get_results_dir()}/{study.save_name}", stand_alone=True)

    def prepare_and_get_results_dir(self):
        try:
            os.mkdir("results")
        except FileExistsError:
            pass

        try:
            os.mkdir(f"results/{self.name}")
        except FileExistsError:
            pass
        return f"results/{self.name}"

    def prepare_plot_data(self, data_type: DataType, key: str, font_size: int = 20):
        if not self._has_run:
            raise RuntimeError("run() must be called before plotting the results")

        n_plots = getattr(self.solution[0], data_type.value)[key].shape[0]
        if sum(np.array([getattr(sol, data_type.value)[key].shape[0] for sol in self.solution]) != n_plots) != 0:
            raise RuntimeError("All the models must have the same number of dof to be plotted")
        t = np.linspace(self.solution[0].phase_time[0], self.solution[0].phase_time[1], self.solution[0].ns[0] + 1)

        plot_options = self.conditions.plot_options
        studies = self.conditions.studies

        for i in range(n_plots):
            fig = plt.figure()
            fig.set_size_inches(16, 9)
            plt.rcParams["text.usetex"] = True
            plt.rcParams["text.latex.preamble"] = (
                r"\usepackage{amssymb}"
                r"\usepackage{siunitx}"
                r"\newcommand{\condition}{C/}"
                r"\newcommand{\noFatigue}{\varnothing}"
                r"\newcommand{\qcc}{4\textsubscript{CC}}"
                r"\newcommand{\pe}{P\textsubscript{E}}"
                r"\newcommand{\taupm}{\tau^{\pm}}"
                r"\newcommand{\tauns}{\tau^{\times}}"
                r"\newcommand{\condTauNf}{{\condition}{\tau}{\noFatigue}}"
                r"\newcommand{\condTaupm}{{\condition}{\taupm}{}}"
                r"\newcommand{\condTaupmQcc}{{\condition}{\taupm}{\qcc}}"
                r"\newcommand{\condTaupmPe}{{\condition}{\taupm}{\pe}}"
                r"\newcommand{\condTauns}{{\condition}{\tauns}{}}"
                r"\newcommand{\condTaunsNf}{{\condition}{\tauns}{\noFatigue}}"
                r"\newcommand{\condTaunsQcc}{{\condition}{\tauns}{\qcc}}"
                r"\newcommand{\condTaunsPe}{{\condition}{\tauns}{\pe}}"
                r"\newcommand{\condAlpha}{{\condition}{\alpha}{}}"
                r"\newcommand{\condAlphaNf}{{\condition}{\alpha}{\noFatigue}}"
                r"\newcommand{\condAlphaQcc}{{\condition}{\alpha}{\qcc}}"
                r"\newcommand{\condAlphaPe}{{\condition}{\alpha}{\pe}}"
            )

            ax = plt.axes()
            if plot_options.title:
                ax.set_title(plot_options.title % f"{key}\\textsubscript{{{i}}}", fontsize=1.5 * font_size)
            ax.set_xlabel(r"Temps (\SI{}{\second})", fontsize=font_size)
            ax.set_ylabel(
                r"Angle (\SI{}{\degree})" if plot_options.to_degrees else r"Angle (\SI{}{\radian})", fontsize=font_size
            )
            ax.tick_params(axis="both", labelsize=font_size)

            for sol, options in zip(self.solution, plot_options.options):
                data = getattr(sol, data_type.value)[key][i, :]
                data *= 180 / np.pi if plot_options.to_degrees else 1
                plt.plot(t, data, **options)

            if plot_options.legend_indices is not None:
                legend = [study.name if idx else "_" for study, idx in zip(studies, plot_options.legend_indices)]
                ax.legend(legend, loc="lower right", fontsize=font_size, framealpha=0.9)

            if plot_options.maximize:
                plt.get_current_fig_manager().window.showMaximized()

            if plot_options.save_path is not None and plot_options.save_path[i] is not None:
                plt.savefig(f"{self.prepare_and_get_results_dir()}/{plot_options.save_path[i]}", dpi=300)

        self._plots_are_prepared = True

    def _rmse(self, data_type, key, idx_ref: int, sol: Solution):
        data_ref = getattr(self.solution[idx_ref], data_type.value)[key]
        data = getattr(sol, data_type.value)[key]

        e = data_ref - data
        se = e**2
        mse = np.sum(se, axis=1) / data_ref.shape[1]
        rmse = np.sqrt(mse)
        return rmse

    def plot(self):
        if not self._plots_are_prepared:
            raise RuntimeError("At least one plot should be prepared before calling plot")

        plt.show()
