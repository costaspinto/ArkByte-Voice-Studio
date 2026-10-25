import importlib.metadata
import perth

print("resemble-perth distribution:", importlib.metadata.version("resemble-perth"))
print("perth module:", perth.__file__)
print("watermarker class:", perth.PerthImplicitWatermarker)

if perth.PerthImplicitWatermarker is None:
    raise RuntimeError("PerthImplicitWatermarker is None; the upstream fix did not load")

watermarker = perth.PerthImplicitWatermarker()
print("watermarker instance:", type(watermarker).__name__)
print("PERTH_WATERMARKER_READY")