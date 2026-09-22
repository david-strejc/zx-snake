import json, time, urllib.request, uuid
H="http://127.0.0.1:8188"
P=('Candid smartphone photo of a Czech car mechanic in his thirties in a navy work jacket, standing in a small '
   'car-repair workshop holding a rugged tablet, looking at the camera with a slight smile. Fluorescent light, a car '
   'on a lift behind him, a painted sign on the wall reads "AUTOSERVIS NOVÁK — OPRAVY VŠECH ZNAČEK". Natural skin '
   'texture, realistic, no retouching.')
def N(c,**i): return {"class_type":c,"inputs":i}
def graph(unet,clip,w,h,steps,seed):
    return {
     "1":N("UNETLoader",unet_name=unet,weight_dtype="default"),
     "2":N("CLIPLoader",clip_name=clip,type="qwen_image",device="default"),
     "3":N("VAELoader",vae_name="qwen_image_2.1_vae_bf16.safetensors"),
     "4":N("TextEncodeQwenImage21",clip=["2",0],prompt=P,negative_prompt="",resolution=1024),
     "5":N("EmptyLatentImage",width=w,height=h,batch_size=1),
     "6":N("KSampler",model=["1",0],positive=["4",0],negative=["4",1],latent_image=["5",0],seed=seed,
           control_after_generate="fixed",steps=steps,cfg=1.0,sampler_name="euler",scheduler="simple",denoise=1.0),
     "7":N("VAEDecode",samples=["6",0],vae=["3",0]),
     "8":N("SaveImage",images=["7",0],filename_prefix=f"qi_{w}x{h}_{unet[13:17]}"),
    }
def run(label,**kw):
    t=time.time()
    r=json.load(urllib.request.urlopen(urllib.request.Request(H+"/prompt",json.dumps({"prompt":graph(**kw),"client_id":str(uuid.uuid4())}).encode(),{"Content-Type":"application/json"})))
    pid=r["prompt_id"]
    while True:
        time.sleep(0.5)
        h=json.load(urllib.request.urlopen(f"{H}/history/{pid}"))
        if h:
            e=h[pid]; st=e["status"]["status_str"]
            ts={m[0]:m[1].get("timestamp") for m in e["status"].get("messages",[])}
            ex=(ts.get("execution_success",0)-ts.get("execution_start",0))/1000 if "execution_start" in ts else None
            f=list(e["outputs"].values())[0]["images"][0]["filename"] if st=="success" else "-"
            print(f"{label:34} {st:8} wall={time.time()-t:6.1f}s  exec={ex:6.1f}s  {f}",flush=True); return
I8,B16="qwen_image_2.1_int8_convrot.safetensors","qwen_image_2.1_bf16.safetensors"
CI8,CB16="qwen3vl_8b_int8_convrot.safetensors","qwen3vl_8b_bf16.safetensors"
run("A int8  1024x1024 25st COLD",unet=I8,clip=CI8,w=1024,h=1024,steps=25,seed=1)
run("B int8  1024x1024 25st warm",unet=I8,clip=CI8,w=1024,h=1024,steps=25,seed=2)
run("C bf16  1024x1024 25st COLD(swap)",unet=B16,clip=CB16,w=1024,h=1024,steps=25,seed=1)
run("D bf16  1024x1024 25st warm",unet=B16,clip=CB16,w=1024,h=1024,steps=25,seed=2)
run("E bf16  2048x2048 25st warm",unet=B16,clip=CB16,w=2048,h=2048,steps=25,seed=3)
run("F bf16  1536x2752 9:16 25st warm",unet=B16,clip=CB16,w=1536,h=2752,steps=25,seed=4)
run("G int8  1536x2752 9:16 25st",unet=I8,clip=CI8,w=1536,h=2752,steps=25,seed=4)
