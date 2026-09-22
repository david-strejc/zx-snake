import json, time, urllib.request, uuid, sys, threading
P=('Candid smartphone photo of a Czech car mechanic in a navy work jacket in a small workshop holding a rugged tablet, '
   'fluorescent light, a car on a lift behind him, realistic skin texture.')
def N(c,**i): return {"class_type":c,"inputs":i}
def graph(w,h,b,seed):
    return {"1":N("UNETLoader",unet_name="qwen_image_2.1_int8_convrot.safetensors",weight_dtype="default"),
     "2":N("CLIPLoader",clip_name="qwen3vl_8b_int8_convrot.safetensors",type="qwen_image",device="default"),
     "3":N("VAELoader",vae_name="qwen_image_2.1_vae_bf16.safetensors"),
     "4":N("TextEncodeQwenImage21",clip=["2",0],prompt=P,negative_prompt="",resolution=1024),
     "5":N("EmptyLatentImage",width=w,height=h,batch_size=b),
     "6":N("KSampler",model=["1",0],positive=["4",0],negative=["4",1],latent_image=["5",0],seed=seed,
           control_after_generate="fixed",steps=25,cfg=1.0,sampler_name="euler",scheduler="simple",denoise=1.0),
     "7":N("VAEDecode",samples=["6",0],vae=["3",0]),
     "8":N("SaveImage",images=["7",0],filename_prefix=f"par_{w}x{h}_b{b}")}
def job(port,w,h,b,seed,out):
    H=f"http://127.0.0.1:{port}"; t=time.time()
    pid=json.load(urllib.request.urlopen(urllib.request.Request(H+"/prompt",json.dumps({"prompt":graph(w,h,b,seed)}).encode(),{"Content-Type":"application/json"})))["prompt_id"]
    while True:
        time.sleep(0.3); h_=json.load(urllib.request.urlopen(f"{H}/history/{pid}"))
        if h_:
            e=h_[pid]; n=len(list(e["outputs"].values())[0]["images"]) if e["status"]["status_str"]=="success" else 0
            out.append((time.time()-t,n)); return
mode=sys.argv[1]
if mode=="batch":
    for (w,h) in [(1024,1024),(1536,2752)]:
        job(8188,w,h,1,99,[])  # warm this resolution
        for b in ([1,2,4,8] if w==1024 else [1,2,4]):
            o=[]; job(8188,w,h,b,b,o); t,n=o[0]
            print(f"batch {w}x{h} b={b}: {t:6.1f}s for {n} img -> {t/n:5.2f} s/img",flush=True)
else:
    ports=[8188+i for i in range(int(sys.argv[2]))]; w,h=map(int,sys.argv[3].split("x"))
    for p in ports: job(p,w,h,1,7,[])  # warm every instance
    o=[]; t=time.time()
    th=[threading.Thread(target=job,args=(p,w,h,1,11+i,o)) for i,p in enumerate(ports)]
    [x.start() for x in th]; [x.join() for x in th]; T=time.time()-t
    print(f"concurrent {len(ports)} instances {w}x{h}: {T:6.1f}s wall for {len(o)} img -> {T/len(o):5.2f} s/img  (each {[round(x[0],1) for x in o]})",flush=True)
