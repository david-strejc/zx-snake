import json, time, urllib.request, threading, sys
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
 "7":N("VAEDecode",samples=["6",0],vae=["3",0]),"8":N("SaveImage",images=["7",0],filename_prefix=f"q_{w}")}
def one(port,w,h,seed):
    H=f"http://127.0.0.1:{port}"
    pid=json.load(urllib.request.urlopen(urllib.request.Request(H+"/prompt",json.dumps({"prompt":g(w,h,seed)}).encode(),{"Content-Type":"application/json"})))["prompt_id"]
    while True:
        time.sleep(0.3); x=json.load(urllib.request.urlopen(f"{H}/history/{pid}"))
        if x:
            if x[pid]["status"]["status_str"]!="success": raise SystemExit("FAIL "+json.dumps(x[pid]["status"])[-300:])
            return
ports=[8188,8189,8190,8191]; seed=[1000]
def lane(port,w,h,n,done):
    for _ in range(n):
        seed[0]+=1; s=seed[0]; one(port,w,h,s); done.append(1)
for (w,h,n) in [(1024,1024,6),(1536,2752,2)]:
    th=[threading.Thread(target=one,args=(p,w,h,50+i)) for i,p in enumerate(ports)]  # warm each GPU at this res
    [t.start() for t in th]; [t.join() for t in th]
    done=[]; t0=time.time()
    th=[threading.Thread(target=lane,args=(p,w,h,n,done)) for p in ports]
    [t.start() for t in th]; [t.join() for t in th]
    T=time.time()-t0
    print(f"4 GPUs {w}x{h}: {len(done)} images in {T:.1f}s -> {T/len(done):.2f} s/img effective, {3600*len(done)/T:.0f} img/h",flush=True)
