import re
import src.output_parser.Parser as Parser
from sarif_om import Tool, ToolComponent, MultiformatMessageString, Run
from src.output_parser.SarifHolder import parseRule, parseResult, isNotDuplicateRule, parseArtifact, \
    parseLogicalLocation, isNotDuplicateLogicalLocation

FINDING = re.compile('.*pakala\.analyzer\[.*\] INFO Found (.* bug)\.')
COVERAGE = re.compile('Symbolic execution finished with coverage (.*).')
FINISHED = re.compile('Nothing to report.|======> Bug found! Need .* transactions. <======')

class Pakala(Parser.Parser):
    NAME = "pakala"
    VERSION = "2022/08/06"
    PORTFOLIO = {
        "delegatecall bug",
        "selfdestruct bug",
        "call bug"
    }

    def __init__(self, task: 'Execution_Task', output: str):

        def skip(line):
            return (
                line.startswith("Analyzing contract at")
                or line.startswith("Starting symbolic execution step...")
                or line.startswith("Symbolic execution finished with coverage")
                or line.startswith("Outcomes: ")
            )
        super().__init__(task, output, True, skip)
        self._errors.discard('EXIT_CODE_1') # there will be an exception in self._fails anyway

        coverage = None
        analysis_completed = False
        traceback = False
        for line in self._lines:
            if m := COVERAGE.match(line):
                coverage = m[1]
            if m := FINDING.match(line):
                self._findings.add(m[1])
            if FINISHED.match(line):
                analysis_completed = True
        if self._lines and not analysis_completed:
            self._messages.add('analysis incomplete')
            if not self._fails and not self._errors:
                self._fails.add('execution failed')

        analysis = { 'vulnerabilities': sorted(self._findings) }
        if coverage:
            analysis['coverage'] = coverage
        self._analysis = [ analysis ]
    
    ## TODO: Sarif
    def parseSarif(self, conkas_output_results, file_path_in_repo):
        resultsList = []
        rulesList = []
        logicalLocationsList = []

        for analysis_result in conkas_output_results["analysis"]:
            rule = parseRule(tool="conkas", vulnerability=analysis_result["vuln_type"])

            logicalLocation = parseLogicalLocation(analysis_result["maybe_in_function"], kind="function")

            result = parseResult(tool="conkas", vulnerability=analysis_result["vuln_type"], uri=file_path_in_repo,
                                 line=int(analysis_result["line_number"]),
                                 logicalLocation=logicalLocation)

            resultsList.append(result)

            if isNotDuplicateRule(rule, rulesList):
                rulesList.append(rule)

            if isNotDuplicateLogicalLocation(logicalLocation, logicalLocationsList):
                logicalLocationsList.append(logicalLocation)

        artifact = parseArtifact(uri=file_path_in_repo)

        tool = Tool(driver=ToolComponent(name="Conkas", version="1.0.0", rules=rulesList,
                                         information_uri="https://github.com/nveloso/conkas",
                                         full_description=MultiformatMessageString(
                                             text="Conkas is based on symbolic execution, determines which inputs cause which program branches to execute, to find potential security vulnerabilities. Conkas uses rattle to lift bytecode to a high level representation.")))

        run = Run(tool=tool, artifacts=[artifact], logical_locations=logicalLocationsList, results=resultsList)

        return run
