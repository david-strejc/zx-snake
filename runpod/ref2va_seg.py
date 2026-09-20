import json, urllib.request, sys
PROMPT = """subject_definitions:
<Subject 1> is the service technician in <Picture 1>: a man around 35 with short dark-blond hair, light stubble and a dark navy work jacket with grey piping.
<Audio 1> is the complete Czech narrator voiceover track and is reused 1:1 as the target video's spoken audio layer; no character on screen speaks.
summary:
[reference generation + audio reuse] A 12-second vertical documentary-style testimonial cut to <Audio 1>, a sequence of hard-cut shots.
retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - face, hair and clothing retained.
<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete narration.
detailed_description:
The target video is a calm, believable vertical 9:16 documentary-style testimonial for a Czech car-service company, photorealistic, Central European people, handheld phone footage, hard cuts, no on-screen text, no subtitles, no logos.
[Shot 1] <Subject 1> sits at a scratched workshop bench writing into a battered paper service book with a ballpoint pen, a coffee-stained page, an old mobile phone lying beside it; static medium close-up from over his shoulder, the camera shakes slightly with small amplitude at slow speed.
[Shot 2] At 00:03.500, the shot cuts to the old mobile phone lighting up and buzzing on the bench; <Subject 1> picks it up, listens, and rubs his forehead; handheld medium shot.
[Shot 3] At 00:07.600, the shot cuts to <Subject 1> crouched in a narrow parts aisle pulling a cardboard box off a low shelf, the phone clamped to his shoulder, frowning; the camera trucks left with small amplitude at slow speed.
overall_soundscape: The copied audio from <Audio 1> leads throughout. Workshop room tone, a pen scratching on paper, a phone buzzing on wood, cardboard sliding on a metal shelf.
non_diegetic_music: No music; the score is added in post-production."""
def N(c,**i): return {"class_type":c,"inputs":i}
p={
 "1":N("VAELoader",vae_name="minimax_h3_video_vae_fp16.safetensors"),
 "2":N("VAELoader",vae_name="minimax_h3_audio_vae_fp32.safetensors"),
 "3":N("UNETLoader",unet_name="minimax_h3_ref2va_int8_convrot.safetensors",weight_dtype="default"),
 "4":N("CLIPLoader",clip_name="qwen3vl_32b_minimax_h3_int8_convrot.safetensors",type="minimax",device="default"),
 "5":N("LoraLoaderModelOnly",model=["3",0],lora_name="minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",strength_model=1.0),
 "6":N("LoadImage",image="tech_ref.png"),
 "7":N("LoadAudio",audio="seg1_vo.wav"),
 "8":N("MiniMaxH3ReferenceToVideo",**{"clip":["4",0],"vae":["1",0],"audio_vae":["2",0],"prompt":PROMPT,
       "width":768,"height":1344,"length":294,"ref_image_size":"match",
       "ref_images.ref_image_1":["6",0],"ref_audios.ref_audio_1":["7",0]}),
 "9":N("BasicGuider",model=["5",0],conditioning=["8",0]),
 "10":N("KSamplerSelect",sampler_name="res_multistep"),
 "11":N("BasicScheduler",model=["5",0],scheduler="simple",steps=4,denoise=1.0),
 "12":N("RandomNoise",noise_seed=777),
 "13":N("SamplerCustomAdvanced",noise=["12",0],guider=["9",0],sampler=["10",0],sigmas=["11",0],latent_image=["8",1]),
 "14":N("VAEDecode",samples=["13",0],vae=["1",0]),
 "15":N("VAEDecodeAudio",samples=["13",0],vae=["2",0]),
 "16":N("CreateVideo",images=["14",0],audio=["15",0],fps=24.0,bit_depth=8,color_space="sRGB"),
 "17":N("SaveVideo",video=["16",0],filename_prefix="ref2va_test",format="auto"),
}
req=urllib.request.Request("http://127.0.0.1:8188/prompt",json.dumps({"prompt":p}).encode(),{"Content-Type":"application/json"})
try: r=json.load(urllib.request.urlopen(req,timeout=60))
except urllib.error.HTTPError as e: print("REJECTED",e.code); print(e.read().decode()[:3000]); sys.exit(1)
print("prompt_id",r["prompt_id"]); open("/workspace/ref2va_pid.txt","w").write(r["prompt_id"])
