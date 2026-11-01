from PIL import Image, ImageFilter
import numpy as np
im=Image.open('./crop.png').convert('RGB'); a=np.array(im).astype(float)
H,W,_=a.shape
r,g,b=a[...,0],a[...,1],a[...,2]
gold=(r>140)&(g>100)&(r-b>55)&(r+g>290)
bright=(r+g+b>230)&~((b>140)&(b>r+70))
mask=np.zeros((H,W),bool)
for x0,y0,x1,y1 in [(60,52,126,78),(145,220,228,246)]:   # text on wood
    m=np.zeros((H,W),bool); m[y0:y1,x0:x1]=True; mask|=m&gold
for x0,y0,x1,y1 in [(84,116,110,294),(95,272,198,298)]:  # text on black
    m=np.zeros((H,W),bool); m[y0:y1,x0:x1]=True; mask|=m&bright
mask[294:314,96:198]=True
mask=np.array(Image.fromarray((mask*255).astype('uint8')).filter(ImageFilter.MaxFilter(5)))>0
known=~mask
for _ in range(80):
    if known.all(): break
    acc=np.zeros_like(a); cnt=np.zeros((H,W))
    for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
        sk=np.roll(np.roll(known,dy,0),dx,1); sa=np.roll(np.roll(a,dy,0),dx,1)
        acc+=sa*sk[...,None]; cnt+=sk
    new=(~known)&(cnt>0); a[new]=acc[new]/cnt[new][:,None]; known|=new
c=np.dstack([a,np.full((H,W),255.)]).astype(int); R,G,B=c[...,0],c[...,1],c[...,2]
c[(B>140)&(B>R+70)&(B>G+40),3]=0
small=Image.fromarray(c.astype('uint8')).resize((72,94),Image.BOX)
s=np.array(small).astype(int); s[...,3]=np.where(s[...,3]>140,255,0)
s[(s[...,2]>s[...,0]+25)&(s[...,2]>s[...,1]+10),3]=0
rgb=Image.fromarray(s[...,:3].astype('uint8')).quantize(20,method=Image.MEDIANCUT).convert('RGB')
out=Image.fromarray(np.dstack([np.array(rgb),s[...,3]]).astype('uint8'))
out.resize((288,376),Image.NEAREST).save('./trophy_px.png')
out.resize((576,752),Image.NEAREST).save('./preview.png')
