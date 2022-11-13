import os, time

VERSION = "2.0.0-pre2"
HOME = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SITE_CFG = os.path.join(HOME,"site_cfg.yaml")
TASK_LOG = "smartbugs.json"
TOOLS_HOME = os.path.join(HOME,"tools")
TOOL_CONFIG = "config.yaml"
TOOL_FINDINGS = "findings.yaml"
TOOL_PARSER = "parser.py"
TOOL_LOG = "result.log"
TOOL_OUTPUT = "result.tar"
PARSER_OUTPUT = "parsed_result.json"
SARIF_OUTPUT = "result.sarif"
