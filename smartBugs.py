#!/usr/bin/env python3

import docker
import yaml
import logging
import argparse
import os
import sys
from datetime import timedelta
from multiprocessing import Pool, Value
from time import time, localtime, strftime
from src.interface.cli import create_parser, DATASET_CHOICES, TOOLS_CHOICES
from src.docker_api.docker_api import analyse_files

cfg_dataset_path = os.path.abspath('config/dataset/dataset.yaml')
with open(cfg_dataset_path , 'r') as ymlfile:
    try:
        cfg_dataset = yaml.safe_load(ymlfile)
    except yaml.YAMLError as exc:
        print(exc)

output_folder =  strftime("%Y%d%m_%H%M", localtime())
logs = open('results/logs/SmartBugs_'+ output_folder +'.log', 'w')
start_time = time()
nb_task_done = Value('i', 0)
total_execution = Value('f', 0)
nb_task = 0

def analyse(args):
    global logs, output_folder, nb_task, nb_task_done, total_execution
    (tool, file) = args

    try:
        start = time()

        sys.stdout.write('\x1b[1;37m' + 'Analysing file [%d/%d]: ' %(nb_task_done.value, nb_task) + '\x1b[0m')
        sys.stdout.write('\x1b[1;34m' + file + '\x1b[0m')
        sys.stdout.write('\x1b[1;37m' + ' [' + tool + ']' + '\x1b[0m' + '\n')

        analyse_files(tool, file, logs, output_folder)

        with nb_task_done.get_lock():
            nb_task_done.value += 1

        with total_execution.get_lock():
            total_execution.value += time() - start

        duration = str(timedelta(seconds=round(time() - start)))
        
        task_sec = nb_task_done.value/(time() - start_time)
        remaining_time = str(timedelta(seconds=round((nb_task - nb_task_done.value) / task_sec)))

        
        sys.stdout.write('\x1b[1;37m' + 'Done [%d/%d, %s]: ' %(nb_task_done.value, nb_task, remaining_time) + '\x1b[0m')
        sys.stdout.write('\x1b[1;34m' + file + '\x1b[0m')
        sys.stdout.write('\x1b[1;37m' + ' [' + tool + '] in ' + duration +' ' + '\x1b[0m' + '\n')
        logs.write('[%d/%d] ' %(nb_task_done.value, nb_task) + file + ' [' + tool + '] in ' + duration + ' \n')
    except Exception as e:
        print(e)
        raise e


def exec_cmd(args: argparse.Namespace):
    global logs, output_folder, nb_task
    logs.write('Arguments passed: ' + str(sys.argv) + '\n')

    files_to_analyze = []

    if args.dataset:
        if args.dataset == ['all']:
            DATASET_CHOICES.remove('all')
            args.dataset = DATASET_CHOICES
        for dataset in args.dataset:
            dataset_path = cfg_dataset[dataset]
            args.file.append(dataset_path)

    for file in args.file:
        #analyse files
        if os.path.basename(file).endswith('.sol'):
            files_to_analyze.append(file)
        #analyse dirs recursively
        elif os.path.isdir(file):
            for root, dirs, files in os.walk(file):
                for name in files:
                    if name.endswith('.sol'):
                        files_to_analyze.append(os.path.join(root,name))
        else:
            print('%s is not a directory or a solidity file' % file)

    if args.tool == ['all']:
        TOOLS_CHOICES.remove('all')
        args.tool = TOOLS_CHOICES

    tasks = []
    for file in files_to_analyze:
        for tool in args.tool:
            results_folder = 'results/' + tool + '/' + output_folder
            if not os.path.exists(results_folder):
                os.makedirs(results_folder)
            
            if args.skip_existing:
                file_name = os.path.splitext(os.path.basename(file))[0]
                folder = os.path.join(results_folder, file_name, 'result.json')
                if os.path.exists(folder):
                    continue
            tasks.append((tool, file))
        
    
    nb_task = len(tasks)
    
    with Pool(processes=args.processes) as pool:
        pool.map(analyse, tasks)

    return logs



if __name__ == '__main__':
    args = create_parser()
    logs = exec_cmd(args)
    elapsed_time = round(time() - start_time)
    if elapsed_time > 60:
        elapsed_time_sec = round(elapsed_time % 60)
        elapsed_time = round(elapsed_time // 60)
        print('Analysis completed. \nIt took %sm %ss to analyse all files.' % (elapsed_time, elapsed_time_sec))
        logs.write('Analysis completed. \nIt took %sm %ss to analyse all files.' % (elapsed_time, elapsed_time_sec))
    else:
        print('Analysis completed. \nIt took %ss to analyse all files.' % elapsed_time)
        logs.write('Analysis completed. \nIt took %ss to analyse all files.' % elapsed_time)
