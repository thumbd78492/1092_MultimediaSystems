import torch
import PIL.Image as Image
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from torchvision.utils import save_image

from math import ceil
from utils import *
from flow_utils import *
from model import DynFilter, DFNet, BMNet

import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--ckpt_bm', type=str, default='Weights/BMNet_weights.pth')
parser.add_argument('--ckpt_df', type=str, default='Weights/DFNet_weights.pth')

parser.add_argument('--save_flow', action='store_true')
parser.add_argument('--vis_flow', action='store_true')

parser.add_argument('--first', type=str, required=True)
parser.add_argument('--second', type=str, required=True)
parser.add_argument('--output', type=str, required=True)
parser.add_argument('--time_step', type=float, default=0.5)

args = parser.parse_args()
args.dict = dict()

torch.backends.cudnn.benchmark = True

args.dict['context_layer'] = nn.Conv2d(3, 64, (7, 7), stride=(1, 1), padding=(3, 3), bias=False)
args.dict['BMNet'] = BMNet()
args.dict['DF_Net'] = DFNet(32,4,16,6)
args.dict['filtering'] = DynFilter()

args.dict['context_layer'].load_state_dict(torch.load('Weights/context_layer.pth'))
args.dict['BMNet'].load_state_dict(torch.load(args.ckpt_bm))
args.dict['DF_Net'].load_state_dict(torch.load(args.ckpt_df))
ReLU = torch.nn.ReLU()

for param in args.dict['context_layer'].parameters():
    param.requires_grad = False
for param in args.dict['BMNet'].parameters():
    param.requires_grad = False
for param in args.dict['DF_Net'].parameters():
    param.requires_grad = False


if torch.cuda.is_available():
    args.dict['BMNet'].cuda()
    args.dict['DF_Net'].cuda()
    args.dict['context_layer'].cuda()
    args.dict['filtering'].cuda()
    ReLU.cuda()
    

I0 = Image.open(args.first)
I1 = Image.open(args.second)

I0, I1 = map(TF.to_tensor, (I0, I1))

I0 = I0.unsqueeze(0).cuda()
I1 = I1.unsqueeze(0).cuda()

divisor = 32.
H = I1.shape[2]
W = I1.shape[3]

H_ = int(ceil(H / divisor) * divisor)
W_ = int(ceil(W / divisor) * divisor)

def single_base_encode(inp, ciphertext, base):
  if base % 2 == 1:
    diff = [i for i in range(0, base//2+1, 1)]
  else:
    diff = [i for i in range(0, base//2, 1)]
  diff += [i for i in range(base//2 * -1, 0, 1)]
  print(diff)
  
  for RGB in range(len(inp)):
    for i in range(len(inp[RGB])):
      for j in range(len(inp[RGB][i])):
        tmp = int(inp[0][RGB][i][j])
        pwd = ciphertext[0][RGB][i][j]

        mod = tmp % base
        
        tmp += diff[pwd-mod]
        
        if tmp < 0:
          tmp += base
        elif tmp > 255:
          tmp -= base
        inp[0][RGB][i][j] = tmp
  return inp

with torch.no_grad():
    F_0_1 = args.dict['BMNet'](F.interpolate(torch.cat((I0, I1), dim=1), (H_, W_), mode='bilinear'), time=0) * 2.0
    F_1_0 = args.dict['BMNet'](F.interpolate(torch.cat((I0, I1), dim=1), (H_, W_), mode='bilinear'), time=1) * (-2.0)
    BM    = args.dict['BMNet'](F.interpolate(torch.cat((I0, I1), dim=1), (H_, W_), mode='bilinear'), time=args.time_step) # V_t_1

    F_0_1 = F.interpolate(F_0_1, (H, W), mode='bilinear')
    F_1_0 = F.interpolate(F_1_0, (H, W), mode='bilinear')
    BM    = F.interpolate(BM, (H, W), mode='bilinear')

    F_0_1[:, 0, :, :] *= W / float(W_)
    F_0_1[:, 1, :, :] *= H / float(H_)
    F_1_0[:, 0, :, :] *= W / float(W_)
    F_1_0[:, 1, :, :] *= H / float(H_)
    BM[:, 0, :, :] *= W / float(W_)
    BM[:, 1, :, :] *= H / float(H_)

    C1 = warp(torch.cat((I0, ReLU(args.dict['context_layer'](I0))), dim=1), (-args.time_step) * F_0_1)   # F_t_0
    C2 = warp(torch.cat((I1, ReLU(args.dict['context_layer'](I1))), dim=1), (1-args.time_step) * F_0_1)  # F_t_1
    C3 = warp(torch.cat((I0, ReLU(args.dict['context_layer'](I0))), dim=1), (args.time_step) * F_1_0)  # F_t_0
    C4 = warp(torch.cat((I1, ReLU(args.dict['context_layer'](I1))), dim=1), (args.time_step-1) * F_1_0)   # F_t_1
    C5 = warp(torch.cat((I0, ReLU(args.dict['context_layer'](I0))), dim=1), BM*(-2*args.time_step))
    C6 = warp(torch.cat((I1, ReLU(args.dict['context_layer'](I1))), dim=1), BM * 2 * (1-args.time_step))

    input = torch.cat((I0,C1,C2,C3,C4,C5,C6,I1),dim=1)
    DF = F.softmax(args.dict['DF_Net'](input),dim=1)

    candidates = input[:,3:-3,:,:]

    R = args.dict['filtering'](candidates[:, 0::67, :, :], DF)
    G = args.dict['filtering'](candidates[:, 1::67, :, :], DF)
    B = args.dict['filtering'](candidates[:, 2::67, :, :], DF)

    I2 = torch.cat((R, G, B), dim=1)

    BM = BM.permute(0, 2, 3, 1).cpu().data.numpy()[0]

    fn, ext = os.path.splitext(args.output)
    if args.save_flow:
        writeFlow('%s-bw.flo' % fn, BM * (-2*args.time_step))  # Save BM_t_0 file
        writeFlow('%s-fw.flo' % fn, BM * 2 * (1-args.time_step)) # Save BM_t_1 file

    if args.vis_flow:
        Image.fromarray(flow2img(BM*(-2*args.time_step))).save('%s-bw.png' % fn)
        Image.fromarray(flow2img(BM * 2 * (1-args.time_step))).save('%s-fw.png' % fn)

    I2_origin = I2.detach().clone()
    base = 5
    cipher = torch.randint(0, base, tuple(I2.shape))
    I2 = single_base_encode(I2, cipher, base)

    # Debug message
    for RGB in range(len(I2)):
      for i in range(len(I2[RGB])):
        for j in range(len(I2[RGB][i])):
          if abs(I2[0][RGB][i][j] - I2_origin[0][RGB][i][j]) > base//2:
            print("fault")
            sys.exit()

    if ext in ['.jpg','.png','.bmp','.jpeg']:
        save_image(I2, '%s'%args.output)
