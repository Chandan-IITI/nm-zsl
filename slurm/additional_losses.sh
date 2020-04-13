#!/usr/bin/env bash

num_runs=$1

experiments_dir="additional_losses"
mkdir -p $experiments_dir
config="multi_proto"
dataset=cub
case "$dataset" in
    cub) mem=64G ;;
    awa) mem=256G ;;
    *) mem=128G ;;
esac

for (( random_seed=1; random_seed<=num_runs; random_seed++ )); do
    for after_fuse_transform_layers in {512} {256-512}; do
        for std in 0.1; do
            for noise_transform_layers in {128} {128-256}; do
                for num_prototypes in 10 25; do
                    for dae_loss_coef in 0.0 0.1 1.0; do
                        for push_protos_apart_loss_coef in 0.0 0.1; do
                            for protos_clf_loss_coef in 0.0 0.1 1.0; do
                                cli_args=$(echo "-c $config -d $dataset --experiments_dir $experiments_dir -s $random_seed" \
                                        "--config.hp.head.after_fuse_transform_layers $after_fuse_transform_layers" \
                                        "--config.hp.head.dae.enabled true" \
                                        "--config.hp.head.noise.std $std" \
                                        "--config.hp.head.noise.transform_layers $noise_transform_layers" \
                                        "--config.hp.head.push_protos_apart.enabled true" \
                                        "--config.hp.head.protos_clf_loss.enabled true" \
                                        "--config.hp.head.dae.loss_coef $dae_loss_coef" \
                                        "--config.hp.head.push_protos_apart.loss_coef $push_protos_apart_loss_coef" \
                                        "--config.hp.head.protos_clf_loss.loss_coef $protos_clf_loss_coef" \
                                        "--config.hp.head.num_prototypes $num_prototypes")
                                # echo "$cli_args"
                                sbatch --mem "$mem" --export=ALL,cli_args="$cli_args" slurm/slurm_lll_job.sh;
                            done
                        done
                    done
                done
            done
        done

        # Baseline
        cli_args="-c $config -d $dataset --experiments_dir $experiments_dir -s $random_seed --config.hp.head.after_fuse_transform_layers $after_fuse_transform_layers"
        # echo "$cli_args"
        sbatch --mem "$mem" --export=ALL,cli_args="$cli_args" slurm/slurm_lll_job.sh;
    done
done
