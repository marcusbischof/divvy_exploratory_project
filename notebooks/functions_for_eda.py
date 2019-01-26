# Developer: Marcus Bischof

# Operations
import pandas as pd
import numpy as np

# For geojson
import json

# Determining if a point is in a polygon referenced from: https://stackoverflow.com/a/43897516/6169225
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon

def create_memory_efficient_pkl():
    """ Function that loads raw .csv data and applies memory efficient transoformations to the data. """

    print('Reading .csv into memory.')
    df = pd.read_csv('../data/raw/divvy_data.csv')

    print('Objects to categories.')
    # Objects with defined ranges (I do this to from_ and to_station because we are just dealing with Chicago)
    for object_to_cat_feature in ['gender', 'usertype', 'events', 'from_station_name', 'to_station_name']:
        df[object_to_cat_feature] = df[object_to_cat_feature].astype('category')

    # We will need to apply space saving operations on the data here to make it more manageable in local memory.
    # df.describe() defaults to numerics, so figure out the ranges for numerics and downsize when possible.
    df.describe().T[['min', 'max']]

    print('Floats to uint8.')
    # Ints with values ranging from 0 to 255 can be stored as uint8
    for small_int_feature in ['day', 'month', 'week', 'hour', 'tripduration', 'dpcapacity_start', 'dpcapacity_end']:
        df[small_int_feature] = df[small_int_feature].astype('uint8')

    print('Floats to unint16.')
    # Ints with values ranging from 0 to 65535 can be stored as uint16
    for med_int_feature in ['year', 'from_station_id']:
        df[small_int_feature] = df[small_int_feature].astype('uint16')

    print('Objs to float64.')
    for sm_float_val in ['latitude_start', 'longitude_start', 'latitude_end', 'longitude_end']:
        df[sm_float_val] = df[sm_float_val].astype('float64')

    # int8 -128 to 127
    df.temperature = df.temperature.astype('int8')

    print('Saving to .pkl.')
    df.to_pickle('../data/raw/divvy_data_small_memory.pkl')
    print('Done.')

def create_slices_of_memory_efficient_pkl():
    """ Function that splits .pkl of divvy data into 10 separate pickles. """

    print('Reading .pkl into memory.')
    df = pd.read_pickle('../data/raw/divvy_data_small_memory.pkl')

    i = 0
    while i < len(df):
        if i == 9000000:
            df[i:-1].to_pickle('../data/interim/df_{}_{}.pkl'.format(i, len(df)))
        else:
            df[i:i+1000000].to_pickle('../data/interim/df_{}_{}.pkl'.format(i, i+1000000))
        i+=1000000
        print('{} rows processed and saved to slice.')
    print('Done.')

def load_geojson_neighborhood_data():
    """ Returns a DataFrame with neighborhood names and polygons. """

    with open('../data/raw/chicago_zip_code_and_neighborhood_map.geojson') as f:
        n_geo = json.load(f)

    data_for_neighborhood_poly_df = []
    # We loop through the data, and only when we have a neighborhood name do we append
    # the to array that we use to create our neighborhood df.
    for feature in n_geo['features']:
        if 'pri_neigh' in feature['properties'].keys():
            data_for_neighborhood_poly_df.append({
                'neighborhood' : feature['properties']['pri_neigh'],
                'polygon' : feature['geometry']['coordinates'][0][0]
            })
    return pd.DataFrame(data_for_neighborhood_poly_df)

def get_neighborhood_containing_point(longitude, latitude, chicago_neighborhood_polygons):
    """ Returns the name of the neighborhood that a given lat long belongs to. """

    for neighborhood_name in chicago_neighborhood_polygons['neighborhood'].unique():
        polygon = Polygon(list(chicago_neighborhood_polygons[chicago_neighborhood_polygons['neighborhood'] == neighborhood_name]['polygon'].values[0])) # create polygon
        point = Point(longitude, latitude) # create point
        if point.within(polygon): # check if a point is in the polygon
            return neighborhood_name

    return 'No Neighborhood'
