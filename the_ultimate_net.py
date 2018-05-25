import os
import sys
from datetime import datetime
from math import ceil
import tensorflow as tf
from chunks import Chunks  # Our data handling class
from constants import NUM_SAMPS_IN_CHUNK, NUM_CHANNELS, CHUNK_SIZE_MS, SAMP_RATE_S
from utility_functions import get_freqs

# To disable warning that building TF from source will make it faster.
# For more information see:
# https://www.tensorflow.org/install/install_sources
# https://stackoverflow.com/questions/41293077/how-to-compile-tensorflow-with-sse4-2-and-avx-instructions

old_tr = sys.gettrace()
sys.settrace(None)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
sys.settrace(old_tr)


# *****************************************************************************
# CONSTANTS
# *****************************************************************************

# Constants that describe the network
NUM_INPUTS = NUM_SAMPS_IN_CHUNK
NUM_INPUTS_FREQ = int(NUM_INPUTS // 2)
NUM_OUTPUTS = 2

# Constants for running and training the network
NUM_EPOCHS = 5  # Default 2000, changed to 5 for code testing purposes
EPOCH_SIZE = 5
BATCH_SIZE = 30
RESTORE = True
IN_MODEL_LOCATION = "Model/ultimate_model_saved_weights.ckpt"
SAVE = True
OUT_MODEL_LOCATION = "Model/ultimate_model_saved_weights.ckpt"


# *****************************************************************************
# Defining the net and layers
# *****************************************************************************
print("Defining layers in tensorflow")

now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
ROOT_LOGDIR = "tf_logs"
LOGDIR = "{}/run-{}/".format(ROOT_LOGDIR, now)

# Input Layer
with tf.name_scope("inputs"):
    X = tf.placeholder(tf.float32, shape=[None, NUM_INPUTS, NUM_CHANNELS, 1], name="X")
    X_freq = tf.placeholder(tf.float32, shape=[None, NUM_INPUTS_FREQ, NUM_CHANNELS, 1], name="X_freq")
    y = tf.placeholder(tf.int32, shape=[None, 2], name="y")

# Group of convolutional layers
with tf.name_scope("convclust1"):
    # ***************
    # Convolution layer for raw network
    # ***************
    # Convolutive Layers

    # Create convolutive maps
    # Number of convolutive maps in layer
    conv1_fmaps_raw = 32
    # Size of each kernel
    conv1_ksize_raw = [int((20 / CHUNK_SIZE_MS) * NUM_SAMPS_IN_CHUNK), NUM_CHANNELS]
    conv1_time_stride_raw = int((10 / CHUNK_SIZE_MS) * NUM_SAMPS_IN_CHUNK)
    conv1_channel_stride_raw = 1
    conv1_stride_raw = [conv1_time_stride_raw, conv1_channel_stride_raw]
    conv1_pad_raw = "SAME"

    # Number of convolutive maps in layer
    conv2_fmaps_raw = 64
    # Size of each kernel
    conv2_ksize_raw = [10, NUM_CHANNELS]
    conv2_time_stride_raw = 1
    conv2_channel_stride_raw = 1
    conv2_stride_raw = [conv2_time_stride_raw, conv2_channel_stride_raw]
    conv2_pad_raw = "SAME"

    conv1_raw = tf.layers.conv2d(X, filters=conv1_fmaps_raw, kernel_size=conv1_ksize_raw, strides=conv1_stride_raw, padding=conv1_pad_raw, activation=tf.nn.relu, name="conv1_raw")

    conv1_output_shape_raw = [-1, ceil(NUM_INPUTS / conv1_time_stride_raw), ceil(NUM_CHANNELS / conv1_channel_stride_raw), conv1_fmaps_raw]

    conv2_raw = tf.layers.conv2d(conv1_raw, filters=conv2_fmaps_raw, kernel_size=conv2_ksize_raw, strides=conv2_stride_raw, padding=conv2_pad_raw, activation=tf.nn.relu, name="conv2_raw")

    conv2_output_shape_raw = [-1, ceil(conv1_output_shape_raw[1] / conv2_time_stride_raw), ceil(conv1_output_shape_raw[2] / conv2_channel_stride_raw), conv2_fmaps_raw]

    # ***************
    # Convolution layer for freqency net
    # ***************
    # Create convolutive maps
    # Number of convolutive maps in layer
    conv1_fmaps_freq = 32
    # Size of each kernel
    conv1_ksize_freq = [15, NUM_CHANNELS]
    conv1_time_stride_freq = 2
    conv1_channel_stride_freq = 1
    conv1_stride_freq = [conv1_time_stride_freq, conv1_channel_stride_freq]
    conv1_pad_freq = "SAME"

    # Number of convolutive maps in layer
    conv2_freq_fmaps_freq = 64
    # Size of each kernel
    conv2_freq_ksize_freq = [10, NUM_CHANNELS]
    conv2_freq_time_stride_freq = 1
    conv2_freq_channel_stride_freq = 1
    conv2_freq_stride_freq = [conv2_freq_time_stride_freq, conv2_freq_channel_stride_freq]
    conv2_freq_pad_freq = "SAME"

    conv1_freq = tf.layers.conv2d(X_freq, filters=conv1_fmaps_freq, kernel_size=conv1_ksize_freq, strides=conv1_stride_freq, padding=conv1_pad_freq, activation=tf.nn.relu, name="conv1_freq")

    conv1_output_shape_freq = [-1, ceil(NUM_INPUTS_FREQ / conv1_time_stride_freq), ceil(NUM_CHANNELS / conv1_channel_stride_freq), conv1_fmaps_freq]

    conv2_freq = tf.layers.conv2d(conv1_freq, filters=conv2_freq_fmaps_freq, kernel_size=conv2_freq_ksize_freq, strides=conv2_freq_stride_freq, padding=conv2_freq_pad_freq, activation=tf.nn.relu, name="conv2_freq")

    conv2_output_shape_freq = [-1, ceil(conv1_output_shape_freq[1] / conv2_freq_time_stride_freq), ceil(conv1_output_shape_freq[2] / conv2_freq_channel_stride_freq), conv2_freq_fmaps_freq]

# Avg Pooling layer
with tf.name_scope("pool3"):
    # Pool3_raw for raw side of network
    pool3_raw = tf.nn.avg_pool(conv2_raw, ksize=[1, 2, 1, 1], strides=[1, 2, 1, 1], padding="VALID")

    pool3_raw_output_shape = [-1, conv2_output_shape_raw[1] // 2, conv2_output_shape_raw[2], conv2_fmaps_raw]

    pool3_raw_flat = tf.reshape(pool3_raw, shape=[-1, conv2_fmaps_raw * pool3_raw_output_shape[1] * pool3_raw_output_shape[2]])

    # Pool3_freq for frequency side of network
    pool3_freq = tf.nn.avg_pool(conv2_freq, ksize=[1, 2, 1, 1], strides=[1, 2, 1, 1], padding="VALID")

    pool3_freq_output_shape = [-1, conv2_output_shape_freq[1] // 2, conv2_output_shape_freq[2], conv2_freq_fmaps_freq]

    pool3_freq_flat = tf.reshape(pool3_freq, shape=[-1, conv2_freq_fmaps_freq * pool3_freq_output_shape[1] * pool3_freq_output_shape[2]])

# Fully connected layer
with tf.name_scope("fc"):
    # Fully connected layer for raw side of network
    fc_raw_num_nodes = 30
    fc_raw = tf.layers.dense(pool3_raw_flat, fc_raw_num_nodes, activation=tf.nn.relu, name="fc_raw")

    # Fully connected layer for frequency side of network
    fc_freq_num_nodes = 20
    fc_freq = tf.layers.dense(pool3_freq_flat, fc_freq_num_nodes, activation=tf.nn.relu, name="fc_freq")

    # Fully connected layer which takes both other fully connected layers as inputs
    fc_combine_num_nodes = 10
    fc_combine = tf.layers.dense(tf.concat([fc_raw, fc_freq], axis=1), fc_combine_num_nodes, activation=tf.nn.relu, name="fc_combine")


# Output Layer
with tf.name_scope("output"):
    logits = tf.layers.dense(fc_combine, NUM_OUTPUTS, name="output")
    Y_prob = tf.nn.sigmoid(logits, name="Y_prob")

# Training nodes
with tf.name_scope("train"):
    float_y = tf.cast(y, tf.float32)
    xentropy = tf.nn.sigmoid_cross_entropy_with_logits(logits=logits, labels=float_y)
    loss = tf.reduce_mean(xentropy)
    optimizer = tf.train.AdamOptimizer()
    training_op = optimizer.minimize(loss)

# Evaluate the network
with tf.name_scope("eval"):
    error_measure = Y_prob - float_y
    mse = tf.reduce_mean(tf.square(error_measure), name='mse')

    error_count = tf.abs(y - tf.cast(tf.round(Y_prob), tf.int32))
    misclassification_rate = tf.reduce_mean(tf.cast(error_count, tf.float32), name='misclassification_rate')

# Initialize the network
with tf.name_scope("init_and_save"):
    init = tf.global_variables_initializer()
    saver = tf.train.Saver()

# Tensorboard stuff
with tf.name_scope("tensorboard"):
    mse_summary = tf.summary.scalar('MSE', mse)
    tb_train_writer = tf.summary.FileWriter(LOGDIR + "_train", tf.get_default_graph())
    tb_test_writer = tf.summary.FileWriter(LOGDIR + "_test", tf.get_default_graph())


# *****************************************************************************
# Functions
# *****************************************************************************

def print_net():
    """Prints debug information"""
    print('X: ', X)
    print('y: ', y)
    print('conv1_raw: ', conv1_raw)
    print('conv2_raw: ', conv2_raw)
    print('pool3_raw: ', pool3_raw)
    print('pool3_rawflat: ', pool3_raw_flat)
    print('fc_raw: ', fc_raw)
    print('logits: ', logits)
    print('Yprob: ', Y_prob)


def evaluate(chunk_batch, model=IN_MODEL_LOCATION):
    print("Preparing to run the network")
    with tf.Session() as sess:
        init.run()

        # Restore variables from disk.
        saver.restore(sess, model)
        print("Model restored.")

        # Get data
        X_test = chunk_batch
        X_test_freq = get_freqs(X_test)

        print('\nComputing...')
        return Y_prob.eval(feed_dict={X: X_test, X_freq: X_test_freq})


# These parts only need to be run if you want to run and train the network
if __name__ == '__main__':
    # *****************************************************************************
    # Data
    # *****************************************************************************
    import random as random
    files = ['HS_D{0:0=2d}'.format(i) for i in range(1, 38)]
    del files[files.index('HS_D11')]
    del files[files.index('HS_D22')]
    random.seed(42)
    random.shuffle(files)

    training_files = files[:int(0.8 * len(files))]
    testing_files = files[int(0.8 * len(files)):]

    print("Reading in training data")
    train_data = Chunks(training_files, CHUNK_SIZE_MS, samp_rate=SAMP_RATE_S)
    print("Reading in test data")
    test_data = Chunks(testing_files, CHUNK_SIZE_MS, samp_rate=SAMP_RATE_S)

    # *****************************************************************************
    # Running and training the network
    # *****************************************************************************
    print("Preparing to run the network")
    with tf.Session() as sess:
        init.run()

        # Restore variables from disk.
        if RESTORE:
            saver.restore(sess, IN_MODEL_LOCATION)
            print("Model restored.")

        print('\n*****Printing Network Structure*****')
        print_net()

        print('\n*****Pre-training accuracy*****')
        # Measure accuracy
        X_test, y_test = test_data.get_rand_batch(int((11 * 60 * SAMP_RATE_S / NUM_SAMPS_IN_CHUNK) / 1))

        X_test_freq = get_freqs(X_test)

        acc_test, percent_misclassified = sess.run([mse, misclassification_rate], feed_dict={X: X_test, X_freq: X_test_freq, y: y_test})
        # Percent Mis-classified
        print('Test MSE:', acc_test, 'percent_misclassified:', percent_misclassified)

        best_test_mse = acc_test * 10
        best_test_percent_misclassified = 1

        print('\n*****Training the net*****')

        for epoch in range(NUM_EPOCHS):
            for i in range(EPOCH_SIZE):
                # Get data
                X_batch, y_batch = train_data.get_rand_batch(BATCH_SIZE)
                X_batch_freq = get_freqs(X_batch)

                # Train
                sess.run(training_op, feed_dict={X: X_batch, X_freq: X_batch_freq, y: y_batch})

            # Measure accuracy
            acc_train, train_summary = sess.run([mse, mse_summary], feed_dict={X: X_batch, X_freq: X_batch_freq, y: y_batch})

            acc_test, percent_misclassified, test_summary = sess.run([mse, misclassification_rate, mse_summary], feed_dict={X: X_test, X_freq: X_test_freq, y: y_test})

            # Print Percent Mis-classified
            print("{:03d}  Train MSE: {:1.8f}  Test MSE: {:1.8f}  Percent misclassified: {:1.6f}".format(epoch, acc_train, acc_test, percent_misclassified))

            # Log accuracy for Tensorboard reports
            if True:  # i % 10 == 0:
                step = epoch  # * EPOCH_SIZE + i
                tb_test_writer.add_summary(test_summary, step)
                tb_train_writer.add_summary(train_summary, step)

            # Save periodically in case of crashes and @!$#% windows updates
            if acc_test < best_test_mse:  # SAVE and epoch % 2 == 0:
                best_test_mse = acc_test
                best_test_percent_misclassified = percent_misclassified
                save_path = saver.save(sess, OUT_MODEL_LOCATION)
                print("* New lowest model! Saved as: %s" % save_path)

        # Save the variables to disk
        if SAVE:
            save_path = saver.save(sess, OUT_MODEL_LOCATION)
            print("Model saved in file: %s" % save_path)

        print("The best model had a percent misclassified of", best_test_percent_misclassified)