import json, urllib.request, sys
HOST="http://127.0.0.1:8188"
SEED=7
PROMPT=("A fluffy pink cat dancing energetically on a glowing nightclub dance floor. "
        "It bobs its head to the beat, sways its hips side to side, waves its raised paw "
        "rhythmically and swishes its tail. Pink and magenta neon lights pulse and sweep, "
        "disco ball sparkles rotate, light haze drifts. Handheld vertical phone video, "
        "photorealistic fur motion, energetic upbeat dance music, 24fps.")
def N(c,**i): return {"class_type":c,"inputs":i}
p={
 "127":N("VAELoader",vae_name="minimax_h3_video_vae_fp16.safetensors"),
 "128":N("VAELoader",vae_name="minimax_h3_audio_vae_fp32.safetensors"),
 "135":N("UNETLoader",unet_name="minimax_h3_fl2va_int8_convrot.safetensors",weight_dtype="default"),
 "136":N("CLIPLoader",clip_name="qwen3vl_32b_minimax_h3_int8_convrot.safetensors",type="minimax",device="default"),
 "200":N("LoadImage",image="cat_start.png"),
 "147":N("PrimitiveBoolean",value=True),
 "145":N("PrimitiveInt",value=20),
 "146":N("PrimitiveInt",value=8),
 "142":N("LoraLoaderModelOnly",model=["135",0],lora_name="minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",strength_model=1.0),
 "143":N("ComfySwitchNode",on_false=["135",0],on_true=["142",0],switch=["147",0]),
 "144":N("ComfySwitchNode",on_false=["145",0],on_true=["146",0],switch=["147",0]),
 "141":N("PrimitiveFloat",value=6.0),
 "140":N("ComfyMathExpression",**{"values.a":["141",0],"expression":"max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17"}),
 "139":N("MiniMaxH3ImageToVideo",clip=["136",0],vae=["127",0],prompt=PROMPT,width=768,height=1344,length=["140",1],first_frame=["200",0]),
 "134":N("BasicGuider",model=["143",0],conditioning=["139",0]),
 "131":N("KSamplerSelect",sampler_name="res_multistep"),
 "132":N("BasicScheduler",model=["143",0],scheduler="simple",steps=["144",0],denoise=1.0),
 "137":N("RandomNoise",noise_seed=SEED),
 "133":N("SamplerCustomAdvanced",noise=["137",0],guider=["134",0],sampler=["131",0],sigmas=["132",0],latent_image=["139",1]),
 "130":N("VAEDecode",samples=["133",0],vae=["127",0]),
 "129":N("VAEDecodeAudio",samples=["133",0],vae=["128",0]),
 "138":N("CreateVideo",images=["130",0],audio=["129",0],fps=24.0,bit_depth=8,color_space="sRGB"),
 "201":N("SaveVideo",video=["138",0],filename_prefix="cat_tiktok",format="auto"),
}
req=urllib.request.Request(HOST+"/prompt",json.dumps({"prompt":p}).encode(),{"Content-Type":"application/json"})
try: r=json.load(urllib.request.urlopen(req,timeout=60))
except urllib.error.HTTPError as e:
    print("SUBMIT ERROR",e.code); print(e.read().decode()[:3000]); sys.exit(1)
print("prompt_id",r["prompt_id"]); open("/workspace/cat_pid.txt","w").write(r["prompt_id"])
