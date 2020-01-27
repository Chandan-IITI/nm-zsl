import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim.lr_scheduler import ExponentialLR, StepLR
from torch.utils.data import Dataset, DataLoader
from torchvision.models.resnet import resnet50
import torchvision.transforms as T
from firelab.base_trainer import BaseTrainer
from firelab.config import Config

from src.dataloaders.cub import CUB
from src.dataloaders.load_data import load_data
from src.utils.losses import LabelSmoothingLoss
from src.models.classifier import resnet_embedder_forward
from src.utils.model_utils import filter_params
from src.utils.constants import RESNET_FEAT_DIM


class ClassifierTrainer(BaseTrainer):
    """
    Just a normal classifier trainer
    """
    def __init__(self, config: Config):
        super(ClassifierTrainer, self).__init__(config)

    def init_models(self):
        if self.config.hp.model.type == 'resnet50':
            self.model = resnet50(pretrained=self.config.hp.get('pretrained'))
            self.model.fc = nn.Linear(self.model.fc.weight.shape[1], self.config.data.num_classes)
            nn.init.kaiming_normal_(self.model.fc.weight.data)
        elif self.config.hp.model.type == 'resnet-head':
            self.model = nn.Sequential(
                nn.Dropout(0.5),
                nn.Linear(RESNET_FEAT_DIM[self.config.hp.model.resnet_type], self.config.hp.model.hid_dim),
                nn.ReLU(),
                nn.Linear(self.config.hp.model.hid_dim, self.config.data.num_classes)
            )
        else:
            raise NotImplementedError(f'Unknown model: {self.config.hp.model.type}')

        self.model = self.model.to(self.device_name)

    def init_dataloaders(self):
        if self.config.data.name == 'CUB':
            train_transform = T.Compose([
                T.ToPILImage(),
                T.RandomResizedCrop(self.config.hp.img_target_shape),
                T.RandomHorizontalFlip(),
                T.ToTensor(),
                T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225))
            ])
            test_transform = T.Compose([
                T.ToPILImage(),
                T.Resize(self.config.hp.img_target_shape),
                T.CenterCrop(self.config.hp.img_target_shape),
                T.ToTensor(),
                T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225))
            ])

            ds_train = CUB(self.config.data.dir, train=True, transform=train_transform)
            ds_test = CUB(self.config.data.dir, train=False, transform=test_transform)
        elif self.config.data.name == 'CUB_EMBEDDED':
            ds_train, ds_test, _ = load_data(self.config.data)
            ds_train = [(torch.tensor(x), y) for x, y in ds_train]
            ds_test = [(torch.tensor(x), y) for x, y in ds_test]
        else:
            raise NotImplementedError('Unknwon')

        self.train_dataloader = DataLoader(ds_train, batch_size=self.config.hp.batch_size, shuffle=True)
        self.val_dataloader = DataLoader(ds_test, batch_size=128, shuffle=False)

    def init_optimizers(self):
        if self.config.hp.optim.type == 'adam':
            OptimClass = torch.optim.Adam
        elif self.config.hp.optim.type == 'rmsprop':
            OptimClass = torch.optim.RMSprop
        elif self.config.hp.optim.type == 'sgd':
            OptimClass = torch.optim.SGD
        else:
            raise NotImplementedError(f'Unknown optimizer: {self.config.hp.optim.type}')

        if self.config.hp.model.type == 'resnet50':
            self.optim = OptimClass([
                {'params': filter_params(self.model, 'fc'), 'lr': 0.0005},
                {'params': self.model.fc.parameters(), 'lr': 0.005},
            ], **self.config.hp.optim.kwargs.to_dict())
        else:
            self.optim = OptimClass(self.model.parameters(), **self.config.hp.optim.kwargs.to_dict())

        if self.config.hp.optim.has('scheduler'):
            assert self.config.hp.optim.scheduler.type == "step"

            self.has_scheduler = True
            self.scheduler = StepLR(optimizer=self.optim, **self.config.hp.optim.scheduler.kwargs.to_dict())
        else:
            self.has_scheduler = False

    def init_criterions(self):
        # self.criterion = LabelSmoothingLoss(self.config.data.num_classes)
        self.criterion = nn.CrossEntropyLoss()

    def on_epoch_done(self):
        if self.has_scheduler:
            self.scheduler.step()

    def train_on_batch(self, batch):
        self.model.train()

        x = batch[0].to(self.device_name)
        y = batch[1].to(self.device_name)

        # with torch.no_grad():
        #     feats = resnet_embedder_forward(self.model, x)
        # logits = self.model.fc(feats)
        logits = self.model(x)
        loss = self.criterion(logits, y)
        acc = (logits.argmax(dim=1) == y).float().mean()

        self.optim.zero_grad()
        loss.backward()
        self.optim.step()

        self.writer.add_scalar('train/loss', loss.detach().cpu().item(), self.num_iters_done)
        self.writer.add_scalar('train/acc', acc.detach().cpu().item(), self.num_iters_done)
        self.writer.add_scalar('train/lr', self.optim.param_groups[0]['lr'], self.num_iters_done)

    def validate(self):
        self.model.eval()

        guessed = []
        losses = []

        with torch.no_grad():
            for batch in self.val_dataloader:
                x = batch[0].to(self.device_name)
                y = batch[1].to(self.device_name)
                logits = self.model(x)

                losses.extend(F.cross_entropy(logits, y, reduction='none').cpu().tolist())
                guessed.extend((logits.argmax(dim=1) == y).cpu().tolist())

        self.writer.add_scalar('val/loss', np.mean(losses), self.num_iters_done)
        self.writer.add_scalar('val/acc', np.mean(guessed), self.num_iters_done)