import insightface

app = insightface.app.FaceAnalysis(name="buffalo_sc")
# test different det size to maximize accuracy while not running out of 4 GB ram
app.prepare(ctx_id = 0, det_size = (320, 320))


# feed camera feed into here -> capture image -> run insightface against our pre-embedded database to find smallest cosine similarity