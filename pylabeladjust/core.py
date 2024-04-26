
from pyqtree import Index
from tqdm.auto import tqdm
import math
import random
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def adjust_labels(rectangle_data, speed=None, adjust_by_size=True, radius_scale=1.1, 
                  max_iterations=100, plot_progress=False, margin=0, margin_type='percentage', return_optimization_process=False):
    """
    Adjusts the labels of rectangles in the given rectangle_data DataFrame to avoid overlapping.

    Args:
        rectangle_data (DataFrame): A DataFrame containing the rectangle data.
        speed (float, optional): The speed at which the labels are adjusted. Defaults to None, then it uses 1/2th of the width of the mean rectangle.
        adjust_by_size (bool, optional): Whether to adjust the labels based on the size of the rectangles. Defaults to True.
            radius_scale (float, optional): The scale factor for the repulsion radius. Defaults to 1.1.
        max_iterations (int, optional): The maximum number of iterations to perform. Defaults to 100.
        plot_progress (bool, optional): Whether to plot the progress of label adjustment. Defaults to False.
        margin (int, optional): The the size of the margin to add around the rectangles. Either a percentage, or an absolute value. Defaults to 0. 
        margin_type (str, optional): How to add margins. Options are 'percentage' and 'absolute'. 

    Returns:
        DataFrame: The adjusted rectangle_data DataFrame.
    """
    # Make a copy to avoid modifying the original DataFrame outside this function
    rectangle_data = rectangle_data.copy()

    # Calculate speed if not provided
    if speed is None:
        speed = 0.5 * (rectangle_data['width'].mean() )
        
    # Calculate and apply margin
    if margin_type == 'percentage':
        margin_width = rectangle_data['width'] * margin / 100
    elif margin_type == 'absolute':
        margin_width = margin
        
        
    rectangle_data['x'] -= margin_width
    rectangle_data['y'] -= margin_width
    rectangle_data['width'] += 2 * margin_width
    rectangle_data['height'] += 2 * margin_width
    
    if return_optimization_process:
        optimization_process = []

    # Perform label adjustment iterations
    for _ in tqdm(range(max_iterations)):
        rectangle_data['x_center'] = rectangle_data['x'] + rectangle_data['width'] / 2
        rectangle_data['y_center'] = rectangle_data['y'] + rectangle_data['height'] / 2

        width, height = rectangle_data['width'].max(), rectangle_data['height'].max() + rectangle_data['x'].max() - rectangle_data['height'].max()

        spindex = Index(bbox=(rectangle_data['x'].min(),
                                rectangle_data['y'].min(),
                                rectangle_data['x'].max() + rectangle_data['width'].max(),
                                rectangle_data['y'].max() + rectangle_data['height'].max()), max_items=10, max_depth=200)

        for ix, row in rectangle_data.iterrows():
            spindex.insert(ix, bbox=(row['x'],
                                        row['y'],
                                        row['x'] + row['width'],
                                        row['y'] + row['height']))

    

        for ix, row in rectangle_data.iterrows():
            some_collision = False
            matches = spindex.intersect(bbox=(row['x'],
                                                row['y'],
                                                row['x'] + row['width'],
                                                row['y'] + row['height']))
            if plot_progress:
                # Assuming plot_rectangles is defined elsewhere
                fig, ax = plt.subplots()
                plot_rectangles(ax, rectangle_data[['x', 'y', 'width', 'height']], color='grey')
                plot_rectangles(ax, rectangle_data[['x', 'y', 'width', 'height']].iloc[matches], set_limits=False)
                plot_rectangles(ax, pd.DataFrame(rectangle_data[['x', 'y', 'width', 'height']].iloc[ix]).T, color='blue', set_limits=False)
                plt.show()

            for other_point in matches:
                if ix != other_point:
                    collision = repulse(ix, other_point, rectangle_data, speed, adjust_by_size, radius_scale)
                    some_collision = some_collision or collision
                    if return_optimization_process:
                        process_copy = rectangle_data.copy()
                        process_copy['x'] += margin_width
                        process_copy['y'] += margin_width
                        process_copy['width'] -= 2 * margin_width
                        process_copy['height'] -= 2 * margin_width
                        optimization_process.append(process_copy)
                    

    # Revert margin expansion
    rectangle_data['x'] += margin_width
    rectangle_data['y'] += margin_width
    rectangle_data['width'] -= 2 * margin_width
    rectangle_data['height'] -= 2 * margin_width
    rectangle_data = rectangle_data[['x', 'y', 'width', 'height']]
    if return_optimization_process:
        return rectangle_data, optimization_process 
    else:
        return rectangle_data

def repulse(rect1_idx, rect2_idx, rectangle_data, speed, adjust_by_size, radius_scale):
    """
    Repulses two rectangles based on their positions and sizes.

    Parameters:
    rect1_idx (int): Index of the first rectangle in the rectangle_data DataFrame.
    rect2_idx (int): Index of the second rectangle in the rectangle_data DataFrame.
    rectangle_data (pandas.DataFrame): DataFrame containing rectangle data.
    speed (float): Speed of the repulsion.
    adjust_by_size (bool): Flag indicating whether to adjust the repulsion based on the size of the rectangles.
    radius_scale (float): Scale factor for the collision radius.

    Returns:
    bool: True if a collision occurred and the second rectangle was adjusted, False otherwise.
    """
    
    collision = False
    rect1 = rectangle_data.iloc[rect1_idx]
    rect2 = rectangle_data.iloc[rect2_idx]

    x_dist = rect2['x_center'] - rect1['x_center']
    y_dist = rect2['y_center'] - rect1['y_center']
    dist = math.sqrt(x_dist ** 2 + y_dist ** 2)

    if adjust_by_size:
        size1 = max(rect1['width'], rect1['height'])
        size2 = max(rect2['width'], rect2['height'])
        sphere_collision = dist < radius_scale * (size1 + size2)
        if sphere_collision:
            f = 0.1 * size1 / dist if dist > 0 else 0.1
            dx = x_dist / dist * f * speed if dist > 0 else (0.5 - random.random()) * 0.01 * speed
            dy = y_dist / dist * f * speed if dist > 0 else (0.5 - random.random()) * 0.01 * speed
            rectangle_data.loc[rect2_idx, 'x'] += dx
            rectangle_data.loc[rect2_idx, 'y'] += dy
            collision = True



    # This code is sus...
    up_differential = rect1['y'] + rect1['height'] - rect2['y']
    down_differential = rect2['y'] + rect2['height'] - rect1['y']
    label_collision_x_left = rect2['x'] + rect2['width'] - rect1['x']
    label_collision_x_right = rect1['x'] + rect1['width'] - rect2['x']

    if up_differential > 0 and down_differential > 0 and label_collision_x_left > 0 and label_collision_x_right > 0:
        if up_differential > down_differential:
            rectangle_data.at[rect2_idx, 'y'] -= 0.02 * rect1['height'] * (0.8 + 0.4 * random.random()) * speed
        else:
            rectangle_data.at[rect2_idx, 'y'] += 0.02 * rect1['height'] * (0.8 + 0.4 * random.random()) * speed

        if label_collision_x_left > label_collision_x_right:
            rectangle_data.at[rect2_idx, 'x'] += 0.01 * (rect1['height'] * 2) * (0.8 + 0.4 * random.random()) * speed
        else:
            rectangle_data.at[rect2_idx, 'x'] -= 0.01 * (rect1['height'] * 2) * (0.8 + 0.4 * random.random()) * speed

        collision = True

    return collision





                  
                  

def adjust_texts(texts, speed=None, adjust_by_size=True, radius_scale=1.1, 
                  max_iterations=200, plot_progress=True, margin=0, margin_type='percentage', return_optimization_process=False):
    """
    Adjusts the positions of texts on a plot to avoid overlapping.

    Args:
        texts (List[matplotlib.text.Text]): A list of text objects to be adjusted.
        speed (float, optional): The speed of the adjustment process. Defaults to None, in which case it uses 1/2th of the width of the mean text.
        adjust_by_size (bool, optional): Whether to adjust the texts based on their sizes. Defaults to True.
        radius_scale (float, optional): The scale factor for the radius used in the adjustment process. Defaults to 1.1.
        max_iterations (int, optional): The maximum number of iterations for the adjustment process. Defaults to 200.
        plot_progress (bool, optional): Whether to plot the progress of the adjustment process. Defaults to True.
        margin_percentage (int, optional): The percentage of margin to be added around the adjusted texts. Calculated from the width of rectangles. Defaults to 10.
        return_optimization_process (bool, optional): Whether to return the optimization process. Defaults to False.

    Returns:
        pandas.DataFrame: A DataFrame containing the adjusted positions of the texts.
    """
    ax = plt.gca()
    bbox_list = []
    renderer = ax.figure.canvas.get_renderer()

    for text in texts:
        bbox = text.get_window_extent(renderer).transformed(ax.transData.inverted())
        bbox_list.append([bbox.x0, bbox.y0, bbox.width, bbox.height])
        
    rectangle_df = pd.DataFrame(bbox_list, columns=['x', 'y', 'width', 'height'])
    
    
    if return_optimization_process:
        rectangles_adjusted, optimization_process = adjust_labels(rectangle_df, speed=speed, adjust_by_size=adjust_by_size, radius_scale=radius_scale, max_iterations=max_iterations,
                                        margin=margin, margin_type=margin_type,return_optimization_process=True)
    else:
        rectangles_adjusted = adjust_labels(rectangle_df, speed=speed, adjust_by_size=adjust_by_size, radius_scale=radius_scale, max_iterations=max_iterations,
                                        margin=margin, margin_type=margin_type,return_optimization_process=False)

    new_xs, new_ys = [], []
    print('Resetting positions to accord with alignment')
    for ix, row in rectangles_adjusted.iterrows():
        text = texts[ix]
        ha = text.get_ha()
        va = text.get_va()
        print(ha, va)
        # Reset positions based on ha and va
        if ha == 'center':
            new_x = row['x'] + row['width'] / 2
        elif ha == 'right':
            new_x = row['x'] + row['width']
        else:
            new_x = row['x']

        if va == 'center':
            new_y = row['y'] + row['height'] / 2
        elif va == 'top':
            new_y = row['y'] + row['height']
        else:
            new_y = row['y']

        text.set_position((new_x, new_y))

        new_xs.append(new_x)
        new_ys.append(new_y)
        
    rectangles_adjusted['x'] = new_xs
    rectangles_adjusted['y'] = new_ys

    

    if return_optimization_process:
        return rectangles_adjusted, optimization_process
    else:
        return rectangles_adjusted


def plot_rectangles(ax, rectangles_dataframe, color='red', set_limits=True, facecolor='none', alpha=1.):
    """
    Plot rectangles on the given Axes object.

    Parameters:
    - ax (matplotlib.axes.Axes): The Axes object to plot the rectangles on.
    - rectangles_dataframe (pandas.DataFrame): The DataFrame containing the rectangle coordinates and dimensions.
    - color (str): The color of the rectangle edges. Default is 'red'.
    - set_limits (bool): Whether to set the x and y limits of the Axes based on the rectangle coordinates. Default is True.
    - facecolor (str): The color of the rectangle faces. Default is 'none' (transparent).
    - alpha (float): The transparency of the rectangle faces. Default is 1.0 (fully opaque).
    """
    # Iterate over each rectangle
    for _, row in rectangles_dataframe.iterrows():
        # Create a rectangle patch with scaled width and height
        rectangle = patches.Rectangle((row['x'], row['y']), 
                                        row['width'], row['height'],
                                        linewidth=1, edgecolor=color, facecolor=facecolor, alpha=alpha)

        # Add the patch to the Axes
        ax.add_patch(rectangle)

    # Set limits
    if set_limits:
        ax.set_xlim(rectangles_dataframe['x'].min(), rectangles_dataframe['x'].max() + rectangles_dataframe['width'].max())
        ax.set_ylim(rectangles_dataframe['y'].min(), rectangles_dataframe['y'].max() + rectangles_dataframe['height'].max())

#rectangles_adjusted = adjust_labels(rectangles_standardized,  speed=.01, adjust_by_size=True, radius_scale=1.1, max_iterations=250,margin_percentage=10)

