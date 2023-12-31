import argparse
import numpy
import time
from pathlib import Path
import json
import cv2
import torch
import torch.backends.cudnn as cudnn
from numpy import random

from models.experimental import attempt_load
from utils.datasets import LoadStreams, LoadImages, LoadImages_realSize
from utils.general import check_img_size, check_requirements, check_imshow, non_max_suppression, apply_classifier, \
    scale_coords, xyxy2xywh, strip_optimizer, set_logging, increment_path
from utils.plots import plot_one_box
from utils.torch_utils import select_device, load_classifier, time_synchronized, TracedModel
import time
# import numpy as np
timeDict = dict()

# def plot_images(images, targets):
#     # Plot image grid with labels
#
#     if isinstance(images, torch.Tensor):
#         images = images.cpu().float().numpy()
#     if isinstance(targets, torch.Tensor):
#         targets = targets.cpu().numpy()
#
#     # un-normalise
#     if np.max(images[0]) <= 1:
#         images *= 255
#
#     tl = 3  # line thickness
#     tf = max(tl - 1, 1)  # font thickness
#     bs, _, h, w = images.shape  # batch size, _, height, width
#     bs = min(bs, max_subplots)  # limit plot images
#     ns = np.ceil(bs ** 0.5)  # number of subplots (square)
#
#     # Check if we should resize
#     scale_factor = max_size / max(h, w)
#     if scale_factor < 1:
#         h = math.ceil(scale_factor * h)
#         w = math.ceil(scale_factor * w)
#
#     colors = color_list()  # list of colors
#     mosaic = np.full((int(ns * h), int(ns * w), 3), 255, dtype=np.uint8)  # init
#     for i, img in enumerate(images):
#         if i == max_subplots:  # if last batch has fewer images than we expect
#             break
#
#         block_x = int(w * (i // ns))
#         block_y = int(h * (i % ns))
#
#         img = img.transpose(1, 2, 0)
#         if scale_factor < 1:
#             img = cv2.resize(img, (w, h))
#
#         mosaic[block_y:block_y + h, block_x:block_x + w, :] = img
#         if len(targets) > 0:
#             image_targets = targets[targets[:, 0] == i]
#             boxes = xywh2xyxy(image_targets[:, 2:6]).T
#             classes = image_targets[:, 1].astype('int')
#             labels = image_targets.shape[1] == 6  # labels if no conf column
#             conf = None if labels else image_targets[:, 6]  # check for confidence presence (label vs pred)
#
#             if boxes.shape[1]:
#                 if boxes.max() <= 1.01:  # if normalized with tolerance 0.01
#                     boxes[[0, 2]] *= w  # scale to pixels
#                     boxes[[1, 3]] *= h
#                 elif scale_factor < 1:  # absolute coords need scale if image scales
#                     boxes *= scale_factor
#             boxes[[0, 2]] += block_x
#             boxes[[1, 3]] += block_y
#             for j, box in enumerate(boxes.T):
#                 cls = int(classes[j])
#                 color = colors[cls % len(colors)]
#                 cls = names[cls] if names else cls
#                 if labels or conf[j] > 0.1:  # 0.25 conf thresh
#                     label = '%s' % cls if labels else '%s %.1f' % (cls, conf[j])
#                     plot_one_box(box, mosaic, label=label, color=color, line_thickness=tl)
#
#         # Draw image filename labels
#         if paths:
#             label = Path(paths[i]).name[:40]  # trim to 40 char
#             t_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]
#             cv2.putText(mosaic, label, (block_x + 5, block_y + t_size[1] + 5), 0, tl / 3, [220, 220, 220], thickness=tf,
#                         lineType=cv2.LINE_AA)
#
#         # Image border
#         cv2.rectangle(mosaic, (block_x, block_y), (block_x + w, block_y + h), (255, 255, 255), thickness=3)
#
#     if fname:
#         r = min(1280. / max(h, w) / ns, 1.0)  # ratio to limit image size
#         mosaic = cv2.resize(mosaic, (int(ns * w * r), int(ns * h * r)), interpolation=cv2.INTER_AREA)
#         # cv2.imwrite(fname, cv2.cvtColor(mosaic, cv2.COLOR_BGR2RGB))  # cv2 save
#         Image.fromarray(mosaic).save(fname)  # PIL save
#     return mosaic

def detect(save_img=False):
    t0 = time.time()
    source, weights, view_img, save_txt, imgsz, trace = opt.source, opt.weights, opt.view_img, opt.save_txt, opt.img_size, not opt.no_trace
    save_img = not opt.nosave and not source.endswith('.txt')  # save inference images
    webcam = source.isnumeric() or source.endswith('.txt') or source.lower().startswith(
        ('rtsp://', 'rtmp://', 'http://', 'https://'))

    # Directories
    save_dir = Path(increment_path(Path(opt.project) / opt.name, exist_ok=opt.exist_ok))  # increment run
    (save_dir / 'labels' if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    # Initialize
    set_logging()
    device = select_device(opt.device)
    half = device.type != 'cpu'  # half precision only supported on CUDA

    # Load model
    model = attempt_load(weights, map_location=device)  # load FP32 model

    stride = int(model.stride.max())  # model stride
    imgsz = check_img_size(imgsz, s=stride)  # check img_size

    if trace:
        model = TracedModel(model, device, opt.img_size)

    if half:
        model.half()  # to FP16

    model.eval()
    # Second-stage classifier
    classify = False
    if classify:
        modelc = load_classifier(name='resnet101', n=2)  # initialize
        modelc.load_state_dict(torch.load('weights/resnet101.pt', map_location=device)['model']).to(device).eval()

    # Set Dataloader
    vid_path, vid_writer = None, None
    if webcam:
        view_img = check_imshow()
        cudnn.benchmark = True  # set True to speed up constant images size inference
        dataset = LoadStreams(source, img_size=imgsz, stride=stride)
    else:
        # if opt.img_size%640 ==0:
            dataset = LoadImages(source, img_size=imgsz, stride=stride)
        # else:
        #     dataset = LoadImages_realSize(source, img_size=imgsz, stride=stride)

    # Get names and colors
    names = model.module.names if hasattr(model, 'module') else model.names
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

    # Run inference
    if device.type != 'cpu':
        model(torch.zeros(1, 3, imgsz, imgsz).to(device).type_as(next(model.parameters())))  # run once
    old_img_w = old_img_h = imgsz
    old_img_b = 1

    # t0 = time.time()
    # if opt.img_size%640 == 0:
    for path, img, im0s, h0, w0, vid_cap in dataset:
        # img = numpy.pad(img, pad_width=16,mode='constant',constant_values=0)
        img = torch.from_numpy(img).to(device, non_blocking=True)
        img = img.half() if half else img.float()  # uint8 to fp16/32
        # img_ori = img.cpu().float().numpy()
        # img_ori = img_ori.copy()
        # img_ori = img_ori.transpose(1, 2, 0)
        img /= 255.0  # 0 - 255 to 0.0 - 1.0

        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Warmup
        if device.type != 'cpu' and (old_img_b != img.shape[0] or old_img_h != img.shape[2] or old_img_w != img.shape[3]):
            old_img_b = img.shape[0]
            old_img_h = img.shape[2]
            old_img_w = img.shape[3]
            for i in range(3):
                # import test
                # a = test.TEST_IMG == img
                model(img, augment=opt.augment)[0]

        # Inference
        with torch.no_grad():
            t1 = time_synchronized()
        # with torch.no_grad():
            pred, train_out = model(img, augment=opt.augment)
            t2 = time_synchronized()

        # Apply NMS
        pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres, classes=opt.classes, agnostic=opt.agnostic_nms, multi_label=True)
        # pred = non_max_suppression(pred, opt.conf_thres,  opt.iou_thres, labels=[], multi_label=True)
        t3 = time_synchronized()

        # Apply Classifier
        if classify:
            pred = apply_classifier(pred, modelc, img, im0s)

        # Process detections
        # shapes = [[img.shape[2], img.shape[3]]]
        for i, det in enumerate(pred):  # detections per images

            # scale_coords([old_img_h, old_img_h], det[:, :4], [640,640], [[old_img_h/640, old_img_w/640], [img.shape[2]-old_img_h, img.shape[3]-old_img_w]])  # native-space pred
            if webcam:  # batch_size >= 1
                p, s, im0, frame = path[i], '%g: ' % i, im0s[i].copy(), dataset.count
            else:
                p, s, im0, frame = path, '', im0s, getattr(dataset, 'frame', 0)

            im0 = cv2.resize(im0, (w0, h0))

            p = Path(p)  # to Path
            save_path = str(save_dir / p.name)  # img.jpg
            txt_path = str(save_dir / 'labels' / p.stem) + ('' if dataset.mode == 'images' else f'_{frame}')  # img.txt
            gn = torch.tensor([w0, h0])[[1, 0, 1, 0]]  # normalization gain whwh
            if len(det):
                # Rescale boxes from img_size to im0 size
                # if opt.img_size%640 == 0:
                # det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape)#.round()
                det[:, :4] = scale_coords([old_img_w, old_img_h], det[:, :4], [w0, h0], [[dataset.img_size / w0, dataset.img_size / h0],
                                                                         [(old_img_w - dataset.img_size) / 2,
                                                                          (old_img_h - dataset.img_size) / 2]])
                # else:
                #      det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape)#.round()
                # Print results
                # for c in det[:, -1].unique():
                #     n = (det[:, -1] == c).sum()  # detections per class
                #     s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # add to string

                # Write results
                for *xyxy, conf, cls in det:
                    # save_txt = True
                    if save_txt:  # Write to file
                        xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                        line = (cls, *xywh, conf) if opt.save_conf else (cls, *xywh)  # label format
                        with open(txt_path + '.txt', 'a') as f:
                            f.write(('%g ' * len(line)).rstrip() % line + '\n')

                    if save_img or view_img:  # Add bbox to images
                        label = f'{names[int(cls)]} {conf:.2f}'
                        plot_one_box(xyxy, im0, label=label, color=colors[int(cls)], line_thickness=1)

            # Print time (inference + NMS)
            timeDict[save_path] = t3-t1
            print(f'{s}Done. ({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS')


            # Stream results

            if view_img:
                cv2.imshow(str(p), im0)
                cv2.waitKey(1)  # 1 millisecond

            # Save results (images with detections)
            if save_img:
                if dataset.mode == 'images':
                    cv2.imwrite(save_path, im0)
                    print(f" The images with the result is saved in: {save_path}")
                else:  # 'video' or 'stream'
                    if vid_path != save_path:  # new video
                        vid_path = save_path
                        if isinstance(vid_writer, cv2.VideoWriter):
                            vid_writer.release()  # release previous video writer
                        if vid_cap:  # video
                            fps = vid_cap.get(cv2.CAP_PROP_FPS)
                            w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        else:  # stream
                            fps, w, h = 30, im0.shape[1], im0.shape[0]
                            save_path += '.mp4'
                        vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                    vid_writer.write(im0)
    # else:
    #     for path, img, im0s, vid_cap in dataset:
    #         img = torch.from_numpy(img).to(device)
    #         img = img.half() if half else img.float()  # uint8 to fp16/32
    #         img /= 255.0  # 0 - 255 to 0.0 - 1.0
    #         if img.ndimension() == 3:
    #             img = img.unsqueeze(0)
    #
    #         # Warmup
    #         if device.type != 'cpu' and (old_img_b != img.shape[0] or old_img_h != img.shape[2] or old_img_w != img.shape[3]):
    #             old_img_b = img.shape[0]
    #             old_img_h = img.shape[2]
    #             old_img_w = img.shape[3]
    #             for i in range(3):
    #                 model(img, augment=opt.augment)[0]
    #
    #         # Inference
    #         t1 = time_synchronized()
    #         with torch.no_grad():   # Calculating gradients would cause a GPU memory leak
    #             pred = model(img, augment=opt.augment)[0]
    #         t2 = time_synchronized()
    #
    #         # Apply NMS
    #         pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres, classes=opt.classes, agnostic=opt.agnostic_nms)
    #         t3 = time_synchronized()
    #
    #         # Apply Classifier
    #         if classify:
    #             pred = apply_classifier(pred, modelc, img, im0s)
    #
    #         # Process detections
    #         for i, det in enumerate(pred):  # detections per image
    #             if webcam:  # batch_size >= 1
    #                 p, s, im0, frame = path[i], '%g: ' % i, im0s[i].copy(), dataset.count
    #             else:
    #                 p, s, im0, frame = path, '', im0s, getattr(dataset, 'frame', 0)
    #
    #             p = Path(p)  # to Path
    #             save_path = str(save_dir / p.name)  # img.jpg
    #             txt_path = str(save_dir / 'labels' / p.stem) + ('' if dataset.mode == 'image' else f'_{frame}')  # img.txt
    #             gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
    #             if len(det):
    #                 # Rescale boxes from img_size to im0 size
    #                 det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()
    #
    #                 # Print results
    #                 for c in det[:, -1].unique():
    #                     n = (det[:, -1] == c).sum()  # detections per class
    #                     s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # add to string
    #
    #                 # Write results
    #                 for *xyxy, conf, cls in reversed(det):
    #                     if save_txt:  # Write to file
    #                         xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
    #                         line = (cls, *xywh, conf) if opt.save_conf else (cls, *xywh)  # label format
    #                         with open(txt_path + '.txt', 'a') as f:
    #                             f.write(('%g ' * len(line)).rstrip() % line + '\n')
    #
    #                     if save_img or view_img:  # Add bbox to image
    #                         label = f'{names[int(cls)]} {conf:.2f}'
    #                         plot_one_box(xyxy, im0, label=label, color=colors[int(cls)], line_thickness=1)
    #
    #             # Print time (inference + NMS)
    #             print(f'{s}Done. ({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS')
    #
    #             # Stream results
    #             if view_img:
    #                 cv2.imshow(str(p), im0)
    #                 cv2.waitKey(1)  # 1 millisecond
    #
    #             # Save results (image with detections)
    #             if save_img:
    #                 if dataset.mode == 'image':
    #                     cv2.imwrite(save_path, im0)
    #                     print(f" The image with the result is saved in: {save_path}")
    #                 else:  # 'video' or 'stream'
    #                     if vid_path != save_path:  # new video
    #                         vid_path = save_path
    #                         if isinstance(vid_writer, cv2.VideoWriter):
    #                             vid_writer.release()  # release previous video writer
    #                         if vid_cap:  # video
    #                             fps = vid_cap.get(cv2.CAP_PROP_FPS)
    #                             w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    #                             h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    #                         else:  # stream
    #                             fps, w, h = 30, im0.shape[1], im0.shape[0]
    #                             save_path += '.mp4'
    #                         vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    #                     vid_writer.write(im0)
    if save_txt or save_img:
        s = f"\n{len(list(save_dir.glob('labels/*.txt')))} labels saved to {save_dir / 'labels'}" if save_txt else ''
        #print(f"Results saved to {save_dir}{s}")
    import numpy as np
    totalTime = time.time() - t0
    totalInfNMSTime = np.sum(list(timeDict.values()))
    print(f'Done. ({totalTime:.3f}s)')
    print(np.sum(list(timeDict.values())))
    for item in timeDict.items():
        key, value = item
        timeDict[key] = value, value + (totalTime - totalInfNMSTime)/len(dataset)
    with open(str(save_dir)+'/'+source.split('/')[-1]+'.txt', 'w') as timeF:
        json.dump(timeDict, timeF)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default='yolov7.pt', help='model.pt path(s)')
    parser.add_argument('--source', type=str, default='inference/images', help='source')  # file/folder, 0 for webcam
    parser.add_argument('--img-size', type=int, default=0, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IOU threshold for NMS')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='display results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --class 0, or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default='runs/detect', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--no-trace', action='store_true', help='don`t trace model')
    opt = parser.parse_args()
    print(opt)
    #check_requirements(exclude=('pycocotools', 'thop'))
    with torch.no_grad():
        if opt.update:  # update all models (to fix SourceChangeWarning)
            for opt.weights in ['yolov7.pt']:
                detect()
                strip_optimizer(opt.weights)
        else:
            detect()
