# Developer: Marcus Bischof

# Operations
import pandas as pd
import numpy as np

# For geojson
import json

# Image libs
from PIL import Image, ImageChops
from folium.raster_layers import ImageOverlay

# Determining if a point is in a polygon referenced from: https://stackoverflow.com/a/43897516/6169225
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon

# Maps
import folium
from folium import plugins

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

    print('Creating stations DataFrame.')
    n_hood = load_geojson_neighborhood_data()
    # Create a DataFrame of unique stations, and their point (point == (latitude, longitude)),
    # assuming stations always contain the same lat & long.
    stations = []
    for station in df.from_station_name.unique():
        stations.append({
            'station' : station,
            'lat' : df[df.from_station_name == station].head(1)['latitude_start'].values[0],
            'long' : df[df.from_station_name == station].head(1)['longitude_start'].values[0]
        })
    stations = pd.DataFrame(stations)
    stations['neighborhood'] = stations[['long', 'lat']].apply(lambda x : get_neighborhood_containing_point(x[0], x[1], n_hood), axis = 1)

    print('Adding neighborhoods to the data.')
    df['from_neighborhood'] = df['from_station_name'].apply(lambda x : stations[stations.station == x].values[0][3])
    df['to_neighborhood'] = df['to_station_name'].apply(lambda x : stations[stations.station == x].values[0][3])

    print('Saving stations to .pkl.')
    stations.to_pickle('../data/processed/stations.pkl')

    print('Adding same_station_trip feature.')
    # Create a column that tracks whether a trip ended at the station it started at.
    df['same_station_trip'] = df['from_station_name'] == df['to_station_name']

    print('Adding same_neighborhood feature.')
    # Create a column that tracks whether a trip ended at the station it started at.
    df['same_neighborhood_trip'] = df['from_neighborhood'] == df['to_neighborhood']

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
        print('{} rows processed and saved to slice.'.format(i))
    print('Done.')

def add_neighborhood_overlay_to_map(m, n, c, n_hood):
    """ Add a folium polyline to a folium map obj. """

    folium.PolyLine([[x[1], x[0]] for x in list(n_hood[n_hood.neighborhood == n].values[0][1])], color=c).add_to(m)

def add_neighborhood_overlay_to_map_with_fill(m, n, c, n_hood, fill_weight):
    """ Add a folium polyline to a folium map obj. """

    folium.PolyLine([[x[1], x[0]] for x in list(n_hood[n_hood.neighborhood == n].values[0][1])], color=c, fill_color=c, fill_opacity=fill_weight).add_to(m)

def plot_polylines(m, neighborhood, travel_lines, c, n_hood):
    """ Adds a single neighborhood to a map, alone with routes specified by code calling this method. """

    folium.PolyLine([[x[1], x[0]] for x in list(n_hood[n_hood.neighborhood == neighborhood].values[0][1])], color=c).add_to(m)

    folium.PolyLine(travel_lines, color=c).add_to(m)

def add_points_to_map(m, color, icon, points):
    """ Adds divvy stations to map m. """

    # Plot the stations
    for tup in points.itertuples():
        folium.Marker([tup[1], tup[2]], popup=tup[3], icon=folium.Icon(color=color, icon=icon, prefix='fa')).add_to(m)

def create_chicago_map():
    """ Returns a LeafletJS map of Chicago. """

    return folium.Map([41.8781, -87.6298], zoom_start=11, tiles="CartoDB dark_matter")

# This is someone else's code, I will try to re-research where I found this.
def trim(img):
    """ Trims an image such that it can be an overlay on a folium map. """

    border = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, border)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        img = img.crop(bbox)
    return np.array(img)

def add_image_to_map(m, path, lat_1, long_1, lat_2, long_2):
    """ Adds an image overlay to the requisite map. """

    with Image.open(path) as img:
        image = trim(img)

    # We add our legend as an image.
    ImageOverlay(
        image=image,
        bounds=[[lat_1, long_1], [lat_2, long_2]],
        zindex=1,
    ).add_to(m)
