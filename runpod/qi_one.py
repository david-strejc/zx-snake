import json, time, urllib.request, sys
H="http://127.0.0.1:8188"
P=('Candid smartphone photo of a Czech car mechanic in a navy work jacket in a small workshop holding a rugged tablet, '
   'fluorescent light, a car on a lift behind him, realistic skin texture.')
def N(c,**i): return {"class_type":c,"inputs":i}
def g(w,h,seed): return {"1":N("UNETLoader",unet_name="qwen_image_2.1_int8_convrot.safetensors",weight_dtype="default"),
 "2":N("CLIPLoader",clip_name="qwen3vl_8b_int8_convrot.safetensors",type="qwen_image",device="default"),
 "3":N("VAELoader",vae_name="qwen_image_2.1_vae_bf16.safetensors"),
 "4":N("TextEncodeQwenImage21",clip=["2",0],prompt=P,negative_prompt="",resolution=1024),
 "5":N("EmptyLatentImage",width=w,height=h,batch_size=1),
 "6":N("KSampler",model=["1",0],positive=["4",0],negative=["4",1],latent_image=["5",0],seed=seed,
       control_after_generate="fixed",steps=25,cfg=1.0,sampler_name="euler",scheduler="simple",denoise=1.0),
 "7":N("VAEDecode",samples=["6",0],vae=["3",0]),"8":N("SaveImage",images=["7",0],filename_prefix=f"b_{w}")}
def run(w,h,seed):
    t=time.time(); pid=json.load(urllib.request.urlopen(urllib.request.Request(H+"/prompt",json.dumps({"prompt":g(w,h,seed)}).encode(),{"Content-Type":"application/json"})))["prompt_id"]
    while True:
        time.sleep(0.3); x=json.load(urllib.request.urlopen(f"{H}/history/{pid}"))
        if x:
            s=x[pid]["status"]["status_str"]
            if s!="success": print("FAIL",json.dumps(x[pid]["status"])[:600]); sys.exit(1)
            return time.time()-t
c=run(1024,1024,1); w=[run(1024,1024,s) for s in (2,3,4)]; k=run(1536,2752,5)
print(f"RESULT cold1k={c:.1f}s warm1k={sum(w)/3:.2f}s 2k9x16={k:.1f}s")
