import json, urllib.request, time, os, sys

HOST="http://127.0.0.1:8188"
SEED=42
PROMPT=("Cinematic aerial shot flying over a neon cyberpunk city at night, rain-slick "
        "streets reflecting pink and blue signage, holograms flickering, camera slowly "
        "pushing forward between towering skyscrapers, volumetric fog, film grain, 24fps.")

# --- make a 1344x768 start frame ---
from PIL import Image, ImageDraw
W,H=1344,768
img=Image.new("RGB",(W,H))
px=img.load()
for y in range(H):
    for x in range(0,W,2):
        r=int(20+80*(x/W)); g=int(10+30*(y/H)); b=int(60+150*(1-y/H))
        px[x,y]=(r,g,b); 
        if x+1<W: px[x+1,y]=(r,g,b)
dr=ImageDraw.Draw(img)
for bx in range(60,W,150):
    bh=200+ (bx*37)%420
    dr.rectangle([bx,H-bh,bx+90,H],fill=(15,12,40))
    for wy in range(H-bh+20,H-10,40):
        for wx in range(bx+12,bx+80,26):
            if (wx*wy)%3: dr.rectangle([wx,wy,wx+10,wy+16],fill=(255,180,80))
inp="/workspace/ComfyUI/input"; os.makedirs(inp,exist_ok=True)
img.save(inp+"/h3_start.png")
print("start frame written")

def N(cls,**inp): return {"class_type":cls,"inputs":inp}
p={
 "127":N("VAELoader",vae_name="minimax_h3_video_vae_fp16.safetensors"),
 "128":N("VAELoader",vae_name="minimax_h3_audio_vae_fp32.safetensors"),
 "135":N("UNETLoader",unet_name="minimax_h3_fl2va_int8_convrot.safetensors",weight_dtype="default"),
 "136":N("CLIPLoader",clip_name="qwen3vl_32b_minimax_h3_int8_convrot.safetensors",type="minimax",device="default"),
 "200":N("LoadImage",image="h3_start.png"),
 "147":N("PrimitiveBoolean",value=True),
 "145":N("PrimitiveInt",value=20),
 "146":N("PrimitiveInt",value=8),
 "142":N("LoraLoaderModelOnly",model=["135",0],lora_name="minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",strength_model=1.0),
 "143":N("ComfySwitchNode",on_false=["135",0],on_true=["142",0],switch=["147",0]),
 "144":N("ComfySwitchNode",on_false=["145",0],on_true=["146",0],switch=["147",0]),
 "141":N("PrimitiveFloat",value=5.0),
 "140":N("ComfyMathExpression",**{"values.a":["141",0],"expression":"max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17"}),
 "139":N("MiniMaxH3ImageToVideo",clip=["136",0],vae=["127",0],prompt=PROMPT,width=1344,height=768,length=["140",1],first_frame=["200",0]),
 "134":N("BasicGuider",model=["143",0],conditioning=["139",0]),
 "131":N("KSamplerSelect",sampler_name="res_multistep"),
 "132":N("BasicScheduler",model=["143",0],scheduler="simple",steps=["144",0],denoise=1.0),
 "137":N("RandomNoise",noise_seed=SEED),
 "133":N("SamplerCustomAdvanced",noise=["137",0],guider=["134",0],sampler=["131",0],sigmas=["132",0],latent_image=["139",1]),
 "130":N("VAEDecode",samples=["133",0],vae=["127",0]),
 "129":N("VAEDecodeAudio",samples=["133",0],vae=["128",0]),
 "138":N("CreateVideo",images=["130",0],audio=["129",0],fps=24.0,bit_depth=8,color_space="sRGB"),
 "201":N("SaveVideo",video=["138",0],filename_prefix="h3_test",format="auto"),
}
body=json.dumps({"prompt":p}).encode()
req=urllib.request.Request(HOST+"/prompt",body,{"Content-Type":"application/json"})
try:
    r=json.load(urllib.request.urlopen(req,timeout=60))
except urllib.error.HTTPError as e:
    print("SUBMIT ERROR",e.code); print(e.read().decode()[:2000]); sys.exit(1)
pid=r["prompt_id"]; print("prompt_id",pid)
open("/workspace/h3_pid.txt","w").write(pid)
