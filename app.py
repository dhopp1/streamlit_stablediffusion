import streamlit as stimport hmacimport pandas as pdimport torchimport sysimport gcfrom datetime import datetime, timedeltaimport timeimport osfrom streamlit_server_state import server_state, server_state_lockfrom helper.txt2img import initialize_txt2img, gen_txt2imgfrom helper.img2img import initialize_img2img, gen_img2imgfrom helper.outpainting import initialize_outpainting, gen_outpainting### session initialization/login# last used timeif os.path.exists("metadata/last_used.txt") and "last_used" not in st.session_state:    file = open("metadata/last_used.txt", "r")    st.session_state["last_used"] = datetime.strptime(file.read(), '%Y-%m-%d %H:%M:%S.%f')    file.close()else:    st.session_state["last_used"] = datetime.now() - timedelta(hours=0, minutes=10)# last userif os.path.exists("metadata/user.txt"):    file = open("metadata/user.txt", "r")    st.session_state["last_user"] = file.read()    file.close()else:    st.session_state["last_user"] = "none"if "users_list" not in st.session_state:    st.session_state["users_list"] = pd.read_csv("metadata/user_list.csv")# passworddef check_password():    """Returns `True` if the user had the correct password."""    st.session_state["available"] = (datetime.now() - st.session_state["last_used"]).total_seconds() > 1 # available if last use more than 3 minutes ago            if not(st.session_state["available"]):        st.error(f"""Application in use by [{st.session_state['last_user']}](mailto:{st.session_state["users_list"].loc[lambda x: x.user == st.session_state['last_user'], 'email'].values[0]}). Refresh in 3 minutes, if they have stopped using it you will be able to log in.""")    def password_entered():        """Checks whether a password entered by the user is correct."""        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):            st.session_state["password_correct"] = True            del st.session_state["password"]  # Don't store the password.        else:            st.session_state["password_correct"] = False    # Return True if the password is validated.    if st.session_state.get("password_correct", False):        if st.session_state["available"]:            return True        # show input for user name    st.session_state["user_name"] = st.selectbox(       "User",       st.session_state["users_list"],       index=None,       placeholder="Select user...",    )    # Show input for password.    st.text_input(        "Password", type="password", on_change=password_entered, key="password"    )    if "password_correct" in st.session_state:        st.error("Password incorrect")    return Falseif not check_password():    st.stop()  # Do not continue if check_password is not True.    ###  app setup# headerst.title("Local Stable Diffusion")# Do not continue if a new user has booted off this oneif st.session_state["user_name"] != st.session_state["last_user"] and "user_recorded" in st.session_state:    if "model" in st.session_state:        st.session_state["model"].close_connection()        del st.session_state["model"].llm        del st.session_state["model"]        gc.collect()    st.error(f"""[{st.session_state['last_user']}](mailto:{st.session_state["users_list"].loc[lambda x: x.user == st.session_state['last_user'], 'email'].values[0]}) has logged on. Refresh in 3 minutes, if they have stopped using it you will be able to log in.""")    st.stop()    # record the userif "user_recorded" not in st.session_state:    f = open("metadata/user.txt", "w")    f.write(st.session_state["user_name"])    f.close()    st.session_state["user_recorded"] = True        # clear out the old output images    for file_name in os.listdir("metadata/output_images/"):        os.remove(f"metadata/output_images/{file_name}")    server_state["user_name"] = st.session_state["user_name"]print(f'New user: {server_state["user_name"]}')    # record last interactionf = open("metadata/last_used.txt", "w")f.write(str(datetime.now()))f.close()# styles sheetswith open( "styles/style.css" ) as css:    st.markdown( f'<style>{css.read()}</style>' , unsafe_allow_html= True)    user_avatar = "https://www.svgrepo.com/show/524211/user.svg"#"\N{grinning face}"assistant_avatar = "https://www.svgrepo.com/show/375527/ai-platform.svg"#"\N{Robot Face}"### chat setup# initialize chat historyif "messages" not in st.session_state:    st.session_state.messages = []    # Display chat messages from history on app rerunfor message in st.session_state.messages:    avatar = user_avatar if message["role"] == "user" else assistant_avatar    with st.chat_message(message["role"], avatar=avatar):        if type(message["content"]) == dict:            st.image(message["content"]["image_path"], caption=message["content"]["caption"], output_format="PNG")        else:            st.markdown(message["content"])### directory and model setupif not(os.path.isdir("metadata/models/")):    os.mkdir("metadata/models/")    if not(os.path.isdir("metadata/input_images/")):    os.mkdir("metadata/input_images/")    if not(os.path.isdir("metadata/output_images/")):    os.mkdir("metadata/output_images/")    model_list = pd.read_csv("metadata/model_list.csv")# xlif os.path.isdir(model_list.loc[0, "path"]):    model_name = model_list.loc[0, "path"]else:    model_name = model_list.loc[0, "url"]# outpaintingif os.path.isdir(model_list.loc[1, "path"]):    outpainting_name = model_list.loc[1, "path"]else:    outpainting_name = model_list.loc[1, "url"]    # parametersif torch.cuda.is_available():    device = "cuda"elif torch.backends.mps.is_available() and torch.backends.mps.is_built():    device = "mps"else:    device = "cpu"torch_dtype = torch.float16 if device in ["cuda", "mps"] else None### sidebar# Parametersst.sidebar.markdown("# Model parameters")# manual seedst.session_state["manual_seeds_text"] = st.sidebar.text_input(   "Manual seeds",   value="" if "manual_seeds_text" not in st.session_state else st.session_state["manual_seeds_text"],   help="Manual seed number for reproducibility. Either a single number, or a comma separated list of numbers if number of variations > 1")st.session_state["manual_seeds"] = None if st.session_state["manual_seeds_text"] == "" else [int(x) for x in st.session_state["manual_seeds_text"].split(",")]# upload a photost.session_state["uploaded_file"] = st.sidebar.file_uploader("Upload your own photo", type=[".png"], help="For img2img and outpainting")# number of variationsst.session_state["num_variations"] = st.sidebar.slider(   "num_variations",   min_value=1,   max_value=20,   step=1,   value=1 if "num_variations" not in st.session_state else st.session_state["num_variations"],   help="The number of variations to produce.")# number of inference stepsst.session_state["num_inference_steps"] = st.sidebar.slider(   "num_inference_steps",   min_value=1,   max_value=100,   step=1,   value=25 if "num_inference_steps" not in st.session_state else st.session_state["num_inference_steps"],   help="The number of inference steps.")# guidance scalest.session_state["guidance_scale_text"] = st.sidebar.slider(   "Guidance Scale",   min_value=10,   max_value=300,   step=5,   value=75 if "guidance_scale" not in st.session_state else st.session_state["guidance_scale_text"],   help="Lower = more freedom for the model, higher = more adhesion to the prompt")st.session_state["guidance_scale"] = st.session_state["guidance_scale_text"] / 10# heightst.session_state["height"] = st.sidebar.slider(   "Height",   min_value=8,   max_value=1920,   step=8,   value=512 if "height" not in st.session_state else st.session_state["height"],   help="Height of generated image")# widthst.session_state["width"] = st.sidebar.slider(   "Width",   min_value=8,   max_value=1920,   step=8,   value=512 if "width" not in st.session_state else st.session_state["width"],   help="Width of generated image")# negative promptst.session_state["negative_prompt"] = st.sidebar.text_input(   "Negative prompt",   value="out of frame, lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, mutilated, out of frame, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, blurry, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck, username, watermark, signature." if "negative_prompt" not in st.session_state else st.session_state["negative_prompt"],   help="What not to include in the image.")# strengthst.session_state["strength_text"] = st.sidebar.slider(   "Strength",   min_value=0,   max_value=100,   step=10,   value=50 if "strength" not in st.session_state else st.session_state["strength_text"],   help="Only for img2img. 0 = most coherence to original image, 1 = least")st.session_state["strength"] = st.session_state["strength_text"] / 100# outpaintingst.session_state["outpainting_text"] = st.sidebar.selectbox(    "Outpainting",     options=["Yes", "No"],     index=1 if "outpainting_text" not in st.session_state else ["Yes", "No"].index(st.session_state["outpainting_text"]),    help="If uploaded an image, whether or not to use outpainting or img2img")st.session_state["outpainting"] = True if st.session_state["outpainting_text"] == "Yes" else False ### progress bar  class StreamlitOutputRedirector:    def __init__(self, status_progress, status_text, preceding_text):        self.buffer = ""        self.status_progress = status_progress        self.status_text = status_text        self.preceding_text = preceding_text    def write(self, text):        # Define a keyword to selectively redirect        self.buffer += text    def flush(self):        # Display the captured output        full_text = self.buffer        try:            progress_number = int(full_text[full_text.find("%")-2:full_text.find("%")])        except:            progress_number = 0        progress_timer = full_text.split("|")[-1][1:]        try:             progress_timer = f'time elapsed: {progress_timer.split("<")[0].split("[")[1]} | time remaining: {progress_timer.split("<")[1].split(",")[0]}'        except:            progress_timer = 'time elapsed: 0:00 | time remaining: NA'        self.status_progress = self.status_progress.progress(progress_number)        self.status_text = self.status_text.markdown(f"{self.preceding_text}{progress_timer}")        self.buffer = ""      def clear(self):        # Clear the Streamlit screen by emptying the placeholder        self.status_progress = self.status_progress.empty()        self.status_progress = self.status_text.empty()    def replacePlaceholder(self, newPlaceholder):         self.placeholder = newPlaceholder### accept user input# download any uploaded imageif "uploaded_file" in st.session_state:    if st.session_state["uploaded_file"] is not None:        if os.path.isdir("metadata/input_images/input.png"):            os.remove("metadata/input_images/input.png")        with open("metadata/input_images/input.png", 'wb') as new_file:            new_file.write(st.session_state["uploaded_file"].getbuffer())            new_file.close()def clear_models(keep=[]):    for model in ["txt2img_pipe", "img2img_pipe", "outpainting_pipe"]:        if model not in keep:            if model in st.session_state:                del st.session_state[model]                gc.collect()                if device == "cuda":                    torch.cuda.empty_cache()                    if prompt := st.chat_input('Prompt...'):    # Display user message in chat message container    with st.chat_message("user", avatar=user_avatar):        st.markdown(prompt)    # Add user message to chat history    st.session_state.messages.append({"role": "user", "content": prompt})        # record last interaction    f = open("metadata/last_used.txt", "w")    f.write(str(datetime.now()))    f.close()        # clear the models    if st.session_state.messages[-1]["content"].lower() == "clear":        clear_models()        with st.chat_message("assistant", avatar=assistant_avatar):            st.markdown("Models cleared!")        st.session_state.messages.append({"role": "assistant", "content": "Models cleared!"})    else:        # img2img        if st.session_state["uploaded_file"] is not None and not(st.session_state["outpainting"]):            clear_models(keep=["img2img_pipe"])                        if "img2img_pipe" not in st.session_state:                with st.spinner('Loading model...'):                    st.session_state["img2img_pipe"] = initialize_img2img(                        model_name, model_list.loc[0, "path"], device, torch_dtype                    )                        with st.spinner('Generating...'):                st.session_state["img_paths"] = gen_img2img(                    pipe=st.session_state["img2img_pipe"],                    prompt=st.session_state.messages[-1]["content"],                    device=device,                    num_variations=st.session_state["num_variations"],                    num_inference_steps=st.session_state["num_inference_steps"],                    guidance_scale=st.session_state["guidance_scale"],                    height=st.session_state["height"],                    width=st.session_state["width"],                    manual_seeds=st.session_state["manual_seeds"],                    negative_prompt=st.session_state["negative_prompt"],                    strength=st.session_state["strength"],                )        # outpainting        elif st.session_state["uploaded_file"] is not None and st.session_state["outpainting"]:            clear_models(keep=["outpainting_pipe"])                        if "outpainting_pipe" not in st.session_state:                with st.spinner('Loading model...'):                    st.session_state["outpainting_pipe"] = initialize_outpainting(                        model_name, model_list.loc[1, "path"], device, torch_dtype                    )                        with st.spinner('Generating...'):                st.session_state["img_paths"] = gen_outpainting(                    pipe=st.session_state["outpainting_pipe"],                    prompt=st.session_state.messages[-1]["content"],                    device=device,                    num_variations=st.session_state["num_variations"],                    num_inference_steps=st.session_state["num_inference_steps"],                    guidance_scale=st.session_state["guidance_scale"],                    height=st.session_state["height"],                    width=st.session_state["width"],                    manual_seeds=st.session_state["manual_seeds"],                    negative_prompt=st.session_state["negative_prompt"],                )        # txt2img        else:            clear_models(keep=["txt2img_pipe"])                            if "txt2img_pipe" not in st.session_state:                # progress bar                output_redirector = StreamlitOutputRedirector(status_progress=st.progress(0), status_text=st.empty(), preceding_text="Loading model: ")                sys.stdout = output_redirector                sys.stderr = output_redirector                st.session_state["txt2img_pipe"] = initialize_txt2img(                    model_name, model_list.loc[0, "path"], device, torch_dtype                )                sys.stdout = sys.stdout.clear()                sys.stderr = sys.stderr.clear()                                # progress bar            output_redirector = StreamlitOutputRedirector(status_progress=st.progress(0), status_text=st.empty(), preceding_text="Generating image(s): ")            sys.stdout = output_redirector            sys.stderr = output_redirector            st.session_state["img_paths"] = gen_txt2img(                pipe=st.session_state["txt2img_pipe"],                prompt=st.session_state.messages[-1]["content"],                device=device,                num_variations=st.session_state["num_variations"],                num_inference_steps=st.session_state["num_inference_steps"],                guidance_scale=st.session_state["guidance_scale"],                height=st.session_state["height"],                width=st.session_state["width"],                manual_seeds=st.session_state["manual_seeds"],                negative_prompt=st.session_state["negative_prompt"],            )            sys.stdout = sys.stdout.clear()            sys.stderr = sys.stderr.clear()                    for img_path in st.session_state["img_paths"]:            with st.chat_message("assistant", avatar=assistant_avatar):                st.image(img_path, caption=f"{img_path.split('/')[-1].split('_')[0]}", output_format="PNG")            st.session_state.messages.append({"role": "assistant", "content": {"image_path": img_path, "caption": f"{img_path.split('/')[-1].split('_')[0]}"}})