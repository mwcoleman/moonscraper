## Converts image to flattened one-hot vector of hold positions. Needs work.


import sys
import numpy as np
import os
import skimage
from skimage.transform import resize
from skimage.morphology import area_closing
import matplotlib.pyplot as plt
import logging
import pandas as pd
import pickle

from collections import namedtuple

BoardCoor = namedtuple('BoardCoor', 'ymin xmin ymax xmax')


def config_logger(logger: logging.Logger) -> logging.Logger:
    """
    Standardise logging output
    """

    logger.setLevel(logging.INFO)
    logger.propogate = False

    formatter = logging.Formatter('%(asctime)s: %(levelname)s [%(filename)s:%(lineno)s]: %(message)s')

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)
    return logger

_logger = config_logger(logging.getLogger(__name__))


def find_edges(img: np.ndarray, board_color_norm: float) -> tuple:
    # Return ymin, xmin, ymax, xmax tuple
    board_coors = np.argwhere(np.linalg.norm(img, axis=2) == board_color_norm)
    ymin, ymax = np.min(board_coors[:,0]), np.max(board_coors[:,0])
    xmin, xmax = np.min(board_coors[:,1]), np.max(board_coors[:,1])
    return BoardCoor(ymin, xmin, ymax, xmax)



def find_positions(img_board: np.ndarray, blank_board: np.ndarray, bc_img: BoardCoor, truncate=True) -> np.ndarray:
    '''
    Takes a problem img, and background img (including hold setup) and returns a n-dim boolean signature vector
    With size proportional to shape of blank_board. (i.e. keep blank_board a consistent template image.)

    '''
    # trim
    img_board = img_board[bc_img.ymin:bc_img.ymax, bc_img.xmin:bc_img.xmax]
    # resize to match blank - Crop to hardcoded evenly spaced bolt sizes
    img_board = skimage.transform.resize(img_board, blank_board.shape)
    # Find differences (circles..)
    matched = np.logical_and(img_board, blank_board).astype(float)
    # Each hold centre is spaced in 38,38 pixel blocks.
    matched = matched[47:732, 52:470]
    # Reduce dimension by summing RGBA values and comparing to white (4)
    m = matched.sum(axis=(-1)) == 4
    # Close small dark areas (aliasing artifacts from resize)
    m = skimage.morphology.area_closing(m, area_threshold=100)
    # Invert and close the larger circles to make blobs/connected regios (maybe unecessary)
    m_closed = skimage.morphology.area_closing(~m, area_threshold=10000)
    # plt.imshow(m)
    label_m = skimage.measure.label(m_closed)
    regions = skimage.measure.regionprops(label_m)

    # New image with centroid pixels flagged
    centroid_img = np.zeros_like(label_m)

    for prop in regions:
        y,x = prop.centroid
        # print(prop.centroid)
        centroid_img[int(y), int(x)] = 1.
    
    # Now we reduce dimension to 20 x 13 by maxpooling. 
    # In future (now) we may want to specify grid positions of holds. 

    # y_size = centroid_img.shape[0] // 18
    # x_size = centroid_img.shape[1] // 11

    # assert x_size == y_size and x_size == 38, "Image size error (should be 18 x 11, 38px regions)"

    reduced_m = skimage.measure.block_reduce(
        centroid_img, 
        block_size=(38, 38), 
        func=np.max
    )
    # reduce the n-dim vector
    # return np.floor(reduced_m.ravel()) if truncate else reduced_m.ravel()

    hold_positions = [f'{"ABCDEFGHIJK"[x]}{18-y}' 
                      for (y,x) in np.argwhere(reduced_m)]
    
    return hold_positions[::-1]

def image_to_vector(blank_board_screenshot_path: str, img_screenshot_dir: str):

    blank = plt.imread(blank_board_screenshot_path)

    # TODO: Hardcoded based on the blank board screenshot. May need to adjust x,y
    board_background_colour = np.linalg.norm(blank, axis=2)[700,40]
    bc = find_edges(blank, board_background_colour)
    _logger.info(f'{bc}, {board_background_colour}')

    blank_cropped = blank[bc.ymin:bc.ymax, bc.xmin:bc.xmax]

    # Iterate through screenshot images
    img_paths = [os.path.join(img_screenshot_dir, fp)
                 for fp in os.listdir(img_screenshot_dir)
                 if fp[-3:] in {'png', 'jpg'}]
    
    _logger.info(f"{len(img_paths)} images found in directory.")
    image_vec = {}

    results_dict = {
        'name': [],
        'sequence': []
    }

    for i, fp in enumerate(img_paths):
        name = os.path.split(fp)[1][:-4]
        img = plt.imread(fp)
        img_bc = find_edges(img, board_background_colour)
        vec = find_positions(img, blank_cropped, img_bc, truncate=True)
        # image_vec[name] = vec

        results_dict['name'].append(name)
        results_dict['sequence'].append(vec)

        _logger.info(f"{i}: {name} has {len(vec)} holds")

    pd.DataFrame(results_dict).to_csv('hold_sequences.csv', index=False)
    # pickle.dump(image_vec, "vec.pkl")
    

if __name__ == "__main__":
    image_to_vector(sys.argv[1], sys.argv[2])
