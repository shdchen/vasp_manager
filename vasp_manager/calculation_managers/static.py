# Copyright (c) Dale Gaines II
# Distributed under the terms of the MIT LICENSE

import logging
import os
import subprocess

from vasp_manager.calculation_managers.base import BaseCalculationManager
from vasp_manager.elastic_analysis import analyze_elastic_file, make_elastic_constants
from vasp_manager.vasp_input_creator import VaspInputCreator

logger = logging.getLogger(__name__)


class StaticCalculationManager(BaseCalculationManager):
    """
    Runs static job workflow for a single material
    """

    def __init__(
        self,
        base_path,
        to_rerun,
        to_submit,
        ignore_personal_errors=True,
        from_scratch=False,
        tail=5,
    ):
        """
        For base_path, to_rerun, to_submit, ignore_personal_errors, and from_scratch,
        see BaseCalculationManager

        Args:
            tail (int): number of last lines to log in debugging if job failed
        """
        self.tail = tail
        super().__init__(
            base_path=base_path,
            to_rerun=to_rerun,
            to_submit=to_submit,
            ignore_personal_errors=ignore_personal_errors,
            from_scratch=from_scratch,
        )
        self._results = "not complete"

    @property
    def mode(self):
        return "static"

    @property
    def poscar_source_path(self):
        poscar_source_path = os.path.join(self.base_path, "rlx", "CONTCAR")
        return poscar_source_path

    def setup_calc(self):
        """
        Runs a static SCF calculation through VASP

        By default, requires previous relaxation run
        """
        vasp_input_creator = VaspInputCreator(
            self.calc_path,
            mode=self.mode,
            poscar_source_path=self.poscar_source_path,
            name=self.material_name,
        )
        vasp_input_creator.create()
        if self.to_rerun:
            archive_made = vasp_input_creator.make_archive()
            if not archive_made:
                # set rerun to not make an achive and instead
                # continue to make the input files
                self.to_rerun = False
                self.setup_calc()
                return
        else:
            vasp_input_creator.create()

        if self.to_submit:
            job_submitted = self.submit_job()
            # job status returns True if sucessfully submitted, else False
            if not job_submitted:
                self.setup_calc()

    def check_calc(self):
        """
        Checks result of static calculation

        Returns
            static_successful (bool): if True, static calculation completed successfully
        """
        if not self.job_complete:
            logger.info(f"{self.mode.upper()} job not finished")
            return False

        stdout_path = os.path.join(self.calc_path, "stdout.txt")
        if os.path.exists(stdout_path):
            if not self.job_complete:
                logger.info(f"{self.mode.upper()} not finished")
                return False
            grep_call = f"tail -n{self.tail} {stdout_path}"
            grep_output = (
                subprocess.check_output(grep_call, shell=True).decode("utf-8").strip()
            )
            if "1 F=" in grep_output:
                logger.info(f"{self.mode.upper()} Calculation: SCF converged")
                logger.debug(grep_output)
                return True
            else:
                logger.warning(f"{self.mode.upper()} FAILED")
                logger.debug(grep_output)
                if self.to_rerun:
                    logger.info(f"Rerunning {self.calc_path}")
                    self.setup_calc()
                    return False
        else:
            logger.info(f"{self.mode.upper()} not started")
            return False

    @property
    def is_done(self):
        return self.check_calc()

    @property
    def results(self):
        return self._results

    @results.setter
    def results(self, value):
        if not "done" in value:
            raise Exception
        self._results = value
        return self._results