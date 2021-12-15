#!/usr/bin/env python3

import docker
import os
import sys
import yaml
import tempfile
import requests
from shutil import copyfile, rmtree

from src.execution.execution_task import Execution_Task
from src.logger import logs
from src.utils import get_solc_version,COLERR,COLRESET

client = docker.from_env()

def pull_image(image: str):
    """
    pull images
    """
    try:
        logs.print(f'[DOCKER] pull image: {image} (this may take a while...)')
        client.images.pull(image)
        logs.print(f'[DOCKER] image {image} pulled')
    except docker.errors.APIError as err:
        logs.print(f'[ERROR] [DOCKER] unable to pull {image}')

def mount_volumes(dir_path: str):
    """
    mount volumes
    """
    try:
        volume_bindings = {os.path.abspath(dir_path): {'bind': '/data', 'mode': 'rw'}}
        return volume_bindings
    except os.error as err:
        logs.print(err)


def stop_container(container):
    """
    stop container
    """
    try:
        if container is not None:
            container.stop(timeout=0)
    except (docker.errors.APIError) as err:
        logs.print(err)


def remove_container(container):
    """
    remove container
    """
    try:
        if container is not None:
            container.remove()
    except (docker.errors.APIError) as err:
        logs.print(err)

def tool_conf(tool: str):
    cfg_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'tools', tool + '.yaml')
    with open(cfg_path, 'r', encoding='utf-8') as ymlfile:
        try:
            return yaml.safe_load(ymlfile)
        except yaml.YAMLError as exc:
            logs.print(exc)

def tool_image(cfg, solc_version, is_bytecode = False):
    if not is_bytecode and isinstance(solc_version, int) and solc_version < 5 and 'solc<5' in cfg['docker_image']:
        return cfg['docker_image']['solc<5']
    return cfg['docker_image']['default']

def analyse_files(task: 'Execution_Task'):
    """
    analyse solidity files
    """
    try:
        cfg = tool_conf(task.tool)

        # create result folder with time
        results_folder = task.result_output_path()
        if not os.path.exists(results_folder):
            os.makedirs(results_folder)
        # os.makedirs(os.path.dirname(results_folder), exist_ok=True)

        # check if config file has all required fields
        if task.execution_configuration.is_bytecode:
            cmd_key = 'cmd_bytecode'
        else:
            cmd_key = 'cmd'

        if 'default' not in cfg['docker_image'] or cfg['docker_image'] == None:
            msg = f"{task.tool}: default docker image not provided. Please check you config file."
            logs.print(msg)
            sys.exit(msg)
        elif cmd_key not in cfg or cfg[cmd_key] == None:
            msg = f"{task.tool}: commands not provided. Please check you config file."
            logs.print(msg)
            sys.exit(msg)

        file_name = os.path.basename(task.file)
        file_name = os.path.splitext(file_name)[0]

        working_dir = tempfile.mkdtemp()
        copyfile(task.file, os.path.join(working_dir, os.path.basename(task.file)))
        file = os.path.join(working_dir, os.path.basename(task.file))

        # bind directory path instead of file path to allow imports in the same directory
        volume_bindings = mount_volumes(working_dir)

        image = tool_image(cfg, get_solc_version(file), is_bytecode=task.execution_configuration.is_bytecode)

        cmd = cfg[cmd_key]

        if '{contract}' in cmd:
            cmd = cmd.replace('{contract}', '/data/' + os.path.basename(file))
        else:
            cmd += ' /data/' + os.path.basename(file)
        container = None
        try:
            container = client.containers.run(image,
                                              cmd,
                                              detach=True,
                                              cpu_quota=task.execution_configuration.cpu_quota,
                                              mem_limit=task.execution_configuration.mem_limit,
                                              volumes=volume_bindings)
            try:
                result = container.wait(timeout=task.execution_configuration.timeout)
                task.exit_code = result['StatusCode']
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                # timeout occurred
                # according to the docs, it's ReadTimeout, but for some versions of docker-py, it is actually ConnectionError
                pass
            except Exception as e:
                print(e)
                pass
            output = container.logs().decode('utf8').strip()
            if (output.count('Solc experienced a fatal error') >= 1 or output.count('compilation failed') >= 1):
                msg = 'ERROR: Solc experienced a fatal error. Check the results file for more info'
                logs.print(f"{COLERR}{msg}{COLRESET}", msg)

            if 'output_in_files' in cfg:
                try:
                    with open(os.path.join(task.result_output_path(), 'result.tar'), 'wb') as f:
                        output_in_file = cfg['output_in_files']['folder']
                        bits, _ = container.get_archive(output_in_file)
                        for chunk in bits:
                            f.write(chunk)
                except Exception as e:
                    msg = 'ERROR: could not get file from container. File not analysed.'
                    logs.print(f"{COLERR}{msg}{COLRESET}", msg)
            return output
        finally:
            rmtree(working_dir)
            stop_container(container)
            remove_container(container)

    except (docker.errors.APIError, docker.errors.ContainerError, docker.errors.ImageNotFound) as err:
        logs.print(err)
