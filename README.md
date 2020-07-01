The official implementation of [Normalization Matters in Zero-Shot Learning](http://arxiv.org/abs/2006.11328).

To run the experiments you will first need to install `firelab`:
```
pip install firelab
```

To run ZSL experiments download the [GBU datasets](https://www.mpi-inf.mpg.de/departments/computer-vision-and-machine-learning/research/zero-shot-learning/zero-shot-learning-the-good-the-bad-and-the-ugly/) and preprocess them like in `notebooks/awa2-feats.ipynb`.
Now, you can run the experiments with
```
firelab start configs/zsl.yml --config.dataset awa2
```

To run CZSL experiments, download [SUN dataset](http://cs.brown.edu/~gmpatter/sunattributes.html) and preprocess it with `notebooks/sun-dataset-preprocessing.ipynb` and [CUB dataset](http://www.vision.caltech.edu/visipedia/CUB-200.html).
Next, you can run the experiments:
```
python src/run.py -c attrs_head --dataset sun
```
