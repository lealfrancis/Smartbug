import re
import src.output_parser.Parser as Parser
from sarif_om import Tool, ToolComponent, MultiformatMessageString, Run
from src.output_parser.SarifHolder import parseRule, parseResult, isNotDuplicateRule, parseArtifact, parseLogicalLocation, isNotDuplicateLogicalLocation


FINDINGS = (
    ('checkedCallStateUpdate.csv', 'CheckedCallStateUpdate'),
    ('destroyable.csv', 'Destroyable'),
    ('originUsed.csv',  'OriginUsed'),
    ('reentrantCall.csv', 'ReentrantCall'),
    ('unsecuredValueSend.csv', 'UnsecuredValueSend'),
    ('uncheckedCall.csv', 'UncheckedCall')
)

ANALYSIS_COMPLETE = re.compile(
    f".*{re.escape('+ /vandal/bin/decompile')}"
    f".*{re.escape('+ souffle -F facts-tmp')}"
    f".*{re.escape('+ rm -rf facts-tmp')}",
    re.DOTALL)

MESSAGES = (
    re.compile("(Warning: Deprecated type declaration) used in file types.dl at line"),
)

FAILS = (
    re.compile("Error loading data: (Cannot open fact file)"),
)

class Vandal(Parser.Parser):
    NAME = "vandal"
    VERSION = "2022/08/05"
    PORTFOLIO = { f[1] for f in FINDINGS }

    def __init__(self, task: 'Execution_Task', output: str):
        super().__init__(task, output)
        self._errors.discard('EXIT_CODE_1') # everything fine, no findings; findings => EXIT_CODE_0

        for line in self._lines:
            if Parser.add_match(self._messages, line, MESSAGES):
                continue
            if Parser.add_match(self._fails, line, FAILS):
                continue
            for indicator,finding in FINDINGS:
                if indicator in line:
                    self._findings.add(finding)
                    break
        if self._lines and (not ANALYSIS_COMPLETE.match(output) or 'Cannot open fact file' in self._fails):
            self._messages.add('analysis incomplete')
            if not self._fails and not self._errors:
                self._fails.add('execution failed')
        if 'Cannot open fact file' in self._fails and len(self._fails) > 1:
            self._fails.remove('Cannot open fact file')

        self._analysis = sorted(self._findings)


    ## TODO: Sarif
    def parseSarif(self, conkas_output_results, file_path_in_repo):
        resultsList = []
        rulesList = []
        logicalLocationsList = []

        for analysis_result in conkas_output_results["analysis"]:
            for error in analysis_result['errors']:
                rule = parseRule(
                    tool="conkas", vulnerability=error["vuln_type"])

                function_name = error["maybe_in_function"] if "maybe_in_function" in error else ""
                logical_location = parseLogicalLocation(
                    function_name, kind="function")

                line_number = int(error["line_number"]
                                  ) if "line_number" in error else -1

                result = parseResult(tool="conkas", vulnerability=error["vuln_type"], uri=file_path_in_repo,
                                     line=line_number,
                                     logicalLocation=logical_location)

                resultsList.append(result)

                if isNotDuplicateRule(rule, rulesList):
                    rulesList.append(rule)

                if isNotDuplicateLogicalLocation(logical_location, logicalLocationsList):
                    logicalLocationsList.append(logical_location)

        artifact = parseArtifact(uri=file_path_in_repo)

        tool = Tool(driver=ToolComponent(name="Conkas", version="1.0.0", rules=rulesList,
                                         information_uri="https://github.com/nveloso/conkas",
                                         full_description=MultiformatMessageString(
                                             text="Conkas is based on symbolic execution, determines which inputs cause which program branches to execute, to find potential security vulnerabilities. Conkas uses rattle to lift bytecode to a high level representation.")))

        run = Run(tool=tool, artifacts=[
                  artifact], logical_locations=logicalLocationsList, results=resultsList)

        return run
