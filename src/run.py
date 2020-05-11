import sys; sys.path.append('.')
import argparse
from hashlib import sha256
from typing import List, Dict, Any

import numpy as np
from firelab.config import Config
from firelab.utils.training_utils import fix_random_seed

from src.trainers.lll_trainer import LLLTrainer
from src.utils.constants import DEBUG
from slurm.utils import generate_experiments_from_hpo_grid


DEFAULT_RANDOM_SEED = 1 # np.random.randint(np.iinfo(np.int32).max)


def run(args: argparse.Namespace, config_cli_args: List[str]):
    config = load_config(args, config_cli_args)
    print(config)

    fix_random_seed(config.random_seed, enable_cudnn_deterministic=True, disable_cudnn_benchmark=True)

    if config.has('validation_sequence'):
        run_validation_sequence(config)
    else:
        LLLTrainer(config).start()


def run_validation_sequence(config: Config):
    experiments_vals = generate_experiments_from_hpo_grid(config.validation_sequence.hpo_grid)
    experiments_vals = [{p.replace('|', '.'): v for p, v in exp.items()} for exp in experiments_vals]
    configs = [config.overwrite({'hp': Config(hp)}) for hp in experiments_vals]
    scores = []

    for i, c in enumerate(configs):
        print('<==== Running HPs ====>')
        print(experiments_vals[i])

        c = c.overwrite(Config({
            'lll_setup.num_tasks': c.validation_sequence.num_tasks,
            'logging.save_train_logits': False,
            'logging.print_accuracy_after_task': False,
            'print_unseen_accuracy': False,
            'print_forgetting': True,
        }))
        trainer = LLLTrainer(c)
        trainer.start()

        score = np.mean(trainer.compute_harmonic_mean_accuracy())
        scores.append(score)

    best_config = configs[np.argmax(scores)]
    print('Best found setup:', experiments_vals[np.argmax(scores)])
    print(best_config)

    best_config = best_config.overwrite(Config({'start_task': config.validation_sequence.num_tasks}))
    trainer = LLLTrainer(best_config)
    trainer.start()


def load_config(args: argparse.Namespace, config_cli_args: List[str]) -> Config:
    base_config = Config.load('configs/base.yml')
    curr_config = Config.load(f'configs/{args.config_name}.yml')

    assert curr_config.has(args.dataset)

    # Setting properties from the base config
    config = base_config.all.clone()
    config = config.overwrite(base_config.get(args.dataset))

    # Setting properties from the current config
    config = config.overwrite(curr_config.all)
    config = config.overwrite(curr_config.get(args.dataset))

    # Setting experiment-specific properties
    config.set('experiments_dir', args.experiments_dir)
    config.set('random_seed', args.random_seed)

    # Overwriting with CLI arguments
    config = config.overwrite(Config.read_from_cli())

    hp_hash = sha256(str(config.hp).encode('utf-8')).hexdigest()[:10]
    exp_name = f'{args.config_name}-{args.dataset}-{hp_hash}-{config.random_seed}'
    config.set('exp_name', exp_name)

    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Running LLL trainer')
    parser.add_argument('-d', '--dataset', type=str, help='Dataset')
    parser.add_argument('-s', '--random_seed', type=int, default=DEFAULT_RANDOM_SEED, help='Random seed to fix')
    parser.add_argument('-c', '--config_name', type=str, help='Which config to run?')
    parser.add_argument('--experiments_dir', type=str,
        default=(f'experiments{"-debug" if DEBUG else ""}'),
        help='Directory where all the experiments reside.')

    args, config_args = parser.parse_known_args()

    print('ARGS:', args)
    print('CONFIG_ARGS:', config_args)

    run(args, config_args)
