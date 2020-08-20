import tensorrt as trt
from torch2trt import torch2trt
from mmdet.apis import init_detector

from mmdet2trt.models.builder import build_warper
from mmdet2trt.models.detectors import TwoStageDetectorWarper

import logging
import torch
import time

def mmdet2trt(  config, 
                checkpoint,
                device="cuda:0",
                fp16_mode=False,
                max_workspace_size=1<<25,
                opt_shape_param=None,
                log_level = logging.WARN,
                return_warp_model = False,
                output_names=["num_detections", "boxes", "scores", "classes"]):
    
    device = torch.device(device)

    logging.basicConfig(level=log_level)

    logging.info("load model from config:{}".format(config))
    torch_model = init_detector(config, checkpoint=checkpoint, device=device)
    cfg = torch_model.cfg

    warp_model = build_warper(torch_model, TwoStageDetectorWarper)

    if opt_shape_param is None:
        img_scale = cfg.test_pipeline[1]['img_scale']
        min_scale = min(img_scale)
        max_scale = max(img_scale)
        opt_shape_param = [
            [
                [1, 3, min_scale, min_scale], 
                [1, 3, img_scale[1], img_scale[0]],
                 [1, 3, max_scale, max_scale]
            ]
        ]
    
    dummy_shape = opt_shape_param[0][1]
    dummy_input = torch.rand(dummy_shape).to(device)


    logging.info("model warmup")
    with torch.no_grad():
        result = warp_model(dummy_input)

    logging.info("convert model")
    start = time.time()
    with torch.cuda.device(device), torch.no_grad():
        trt_model = torch2trt(warp_model, [dummy_input],
                              log_level=trt.Logger.WARNING,
                            # log_level=trt.Logger.VERBOSE,
                              fp16_mode=fp16_mode,
                              opt_shape_param=opt_shape_param,
                              max_workspace_size=max_workspace_size,
                              keep_network=False,
                              strict_type_constraints=True,
                              output_names=output_names)

    duration = time.time()-start
    logging.info("convert take time {} s".format(duration))

    if return_warp_model:
        return trt_model, warp_model
    return trt_model


def main():                                                                                                                                                                                                                                      
    parser = ArgumentParser()                                                                                                                                                                                                                    
    parser.add_argument('--config', help='Path to a mmdet Config file')
    parser.add_argument('--checkpoint', help='Path to a mmdet Checkpoint file')
    parser.add_argument('--output', help='Path where tensorrt model will be saved')
    parser.add_argument("--fp16", type=bool, default=True, help="Enable fp16 inference")
    parser.add_argument("--save-engine", type=bool, default=True, help="Enable saving TensorRT engine in a separate file.")
    args = parser.parse_args()
    trt_model = mmdet2trt(args.config, args.checkpoint, fp16_mode=args.fp16)
    torch.save(trt_model.state_dict(), args.save_path)
    if args.save_engine:
        with open(Path(args.save_path).with_suffix(".engine"), "wb") as f:
            f.write(trt_model.state_dict()["engine"])


if if __name__ == "__main__":
    main()
