import torch
from torch import nn as nn
from torch.nn import Flatten, functional as F


class INConvBlock(nn.Module):
    def __init__(self, nin, nout, stride=1, instance_norm=True, act=nn.ReLU(inplace=True)):
        super(INConvBlock, self).__init__()
        self.conv = nn.Conv2d(nin, nout, 3, stride, 1, bias=not instance_norm)
        if instance_norm:
            self.instance_norm = nn.InstanceNorm2d(nout, affine=True)
        else:
            self.instance_norm = None
        self.act = act

    def forward(self, x):
        x = self.conv(x)
        if self.instance_norm is not None:
            x = self.instance_norm(x)
        return self.act(x)


class UNet(nn.Module):

    def __init__(self, input_channels: int, num_blocks, filter_start=32, mlp_size: int = 128):
        super(UNet, self).__init__()
        c = filter_start
        self.mlp_size = mlp_size
        if num_blocks == 4:
            self.down = nn.ModuleList([
                INConvBlock(input_channels + 1, c),
                INConvBlock(c, 2 * c),
                INConvBlock(2 * c, 2 * c),
                INConvBlock(2 * c, 2 * c),  # no downsampling
            ])
            self.up = nn.ModuleList([
                INConvBlock(4 * c, 2 * c),
                INConvBlock(4 * c, 2 * c),
                INConvBlock(4 * c, c),
                INConvBlock(2 * c, c)
            ])
        elif num_blocks == 5:
            self.down = nn.ModuleList([
                INConvBlock(4, c),
                INConvBlock(c, c),
                INConvBlock(c, 2 * c),
                INConvBlock(2 * c, 2 * c),
                INConvBlock(2 * c, 2 * c),  # no downsampling
            ])
            self.up = nn.ModuleList([
                INConvBlock(4 * c, 2 * c),
                INConvBlock(4 * c, 2 * c),
                INConvBlock(4 * c, c),
                INConvBlock(2 * c, c),
                INConvBlock(2 * c, c)
            ])
        elif num_blocks == 6:
            self.down = nn.ModuleList([
                INConvBlock(4, c),
                INConvBlock(c, c),
                INConvBlock(c, c),
                INConvBlock(c, 2 * c),
                INConvBlock(2 * c, 2 * c),
                INConvBlock(2 * c, 2 * c),  # no downsampling
            ])
            self.up = nn.ModuleList([
                INConvBlock(4 * c, 2 * c),
                INConvBlock(4 * c, 2 * c),
                INConvBlock(4 * c, c),
                INConvBlock(2 * c, c),
                INConvBlock(2 * c, c),
                INConvBlock(2 * c, c)
            ])
        self.mlp = nn.Sequential(
            Flatten(),
            nn.Linear(4 * 4 * 2 * c, mlp_size), nn.ReLU(inplace=True),
            nn.Linear(mlp_size, mlp_size), nn.ReLU(inplace=True),
            nn.Linear(mlp_size, 4 * 4 * 2 * c), nn.ReLU(inplace=True)
        )
        self.final_conv = nn.Conv2d(c, 2, 1)

    def forward(self, x):
        batch_size = x.size(0)
        x_down = [x]
        skip = []
        for i, block in enumerate(self.down):
            act = block(x_down[-1])
            skip.append(act)
            if i < len(self.down) - 1:
                act = F.interpolate(act, scale_factor=0.5, mode='nearest', recompute_scale_factor=True)
            x_down.append(act)
        x_up = self.mlp(x_down[-1]).view(batch_size, -1, 4, 4)
        for i, block in enumerate(self.up):
            features = torch.cat([x_up, skip[-1 - i]], dim=1)
            x_up = block(features)
            if i < len(self.up) - 1:
                x_up = F.interpolate(x_up, scale_factor=2.0, mode='nearest')
        return self.final_conv(x_up)
