# For debugging
import sys
old_tr = sys.gettrace()
sys.settrace(None)

from scipy.fftpack import rfft, fft
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from math import ceil
from Chunks import Chunks

# For debugging
sys.settrace(old_tr)

# Info for TensorBoard
from datetime import datetime

now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
root_logdir = "tf_logs"
logdir = "{}/run-{}/".format(root_logdir, now)

# Constants
chunk_size_ms = 250
num_channels = 2
samp_rate_s = 44100 # Vals / s (Hz)
samp_rate_ms = samp_rate_s / 1000 # vals / ms (kHz)
num_samps_in_chunk = int(chunk_size_ms * samp_rate_ms)
num_inputs = num_samps_in_chunk#num_samps_in_chunk // 2 # Real symmetry in Fourier Transform
num_outputs = 2

# For sanity checks, assert that shape1==shape2 at each index in indices
def assert_eq_shapes(shape1, shape2, indices):
    for i in indices:
        errmsg = 'Index ' + str(i) + ': ' + str(shape1[i]) + ' vs ' + str(shape2[i])
        assert shape1[i] == shape2[i], errmsg

# Input Layer
with tf.name_scope("inputs"):
    X = tf.placeholder(tf.float32, shape=[None, num_inputs, num_channels, 1], name="X")
    y = tf.placeholder(tf.int32, shape=[None, 2], name="y")

# Group of convolutional layers
with tf.name_scope("convclust1"):
    # Convolutive Layers

    # Create convolutive maps
    # Number of convolutive maps in layer
    conv1_fmaps = 32
    # Size of each kernel
    conv1_ksize = [15, num_channels]
    conv1_time_stride = 2
    conv1_channel_stride = 1
    conv1_stride = [conv1_time_stride, conv1_channel_stride]
    conv1_pad = "SAME"

    # Number of convolutive maps in layer
    conv2_fmaps = 64
    # Size of each kernel
    conv2_ksize = [10, num_channels]
    conv2_time_stride = 1
    conv2_channel_stride = 1
    conv2_stride = [conv2_time_stride, conv2_channel_stride]
    conv2_pad = "SAME"

    conv1 = tf.layers.conv2d(X, filters=conv1_fmaps, kernel_size=conv1_ksize,
                            strides=conv1_stride, padding=conv1_pad,
                            activation=tf.nn.relu, name="conv1")

    conv1_output_shape = [-1, ceil(num_inputs / conv1_time_stride), ceil(num_channels / conv1_channel_stride), conv1_fmaps]
    assert_eq_shapes(conv1_output_shape, conv1.get_shape(), (1,2,3))

    conv2 = tf.layers.conv2d(conv1, filters=conv2_fmaps, kernel_size=conv2_ksize,
                            strides=conv2_stride, padding=conv2_pad,
                            activation=tf.nn.relu, name="conv2")

    conv2_output_shape = [-1, ceil(conv1_output_shape[1] / conv2_time_stride), ceil(conv1_output_shape[2] / conv2_channel_stride), conv2_fmaps]
    assert_eq_shapes(conv2_output_shape, conv2.get_shape(), (1,2,3))

# Avg Pooling layer
with tf.name_scope("pool3"):
    pool3 = tf.nn.avg_pool(conv2, ksize=[1, 2, 1, 1], strides=[1, 2, 1, 1], padding="VALID")

    pool3_output_shape = [-1, conv2_output_shape[1] // 2, conv2_output_shape[2], conv2_fmaps]
    assert_eq_shapes(pool3_output_shape, pool3.get_shape(), (1,2,3))

    pool3_flat = tf.reshape(pool3, shape=[-1, conv2_fmaps * pool3_output_shape[1] * pool3_output_shape[2]])

# Fully connected layer
with tf.name_scope("fc1"):
    # Number of nodes in fully connected layer
    n_fc1 = 10
    fc1 = tf.layers.dense(pool3_flat, n_fc1, activation=tf.nn.relu, name="fc1")

# Output Layer
with tf.name_scope("output"):
    logits = tf.layers.dense(fc1, num_outputs, name="output")
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
    error = Y_prob - float_y
    mse = tf.reduce_mean(tf.square(error), name='mse')

# Initialize the network
with tf.name_scope("init_and_save"):
    init = tf.global_variables_initializer()
    saver = tf.train.Saver()

with tf.name_scope("tensorboard"):
    mse_summary = tf.summary.scalar('MSE',mse)
    file_write = tf.summary.FileWriter(logdir,tf.get_default_graph())
    
def get_freqs(batch, show=False):
    # Take FFT of each
    for i in range(batch.shape[0]):
        batch[i, :, 0, 0] = np.abs(fft(batch[i, :, 0, 0]))
        batch[i, :, 1, 0] = np.abs(fft(batch[i, :, 1, 0]))

    # Real number symmetry of Fourier Transform
    batch = batch[:,:num_inputs,:,:]

    if(show):
        # Get appropriate time labels
        k = np.arange(num_inputs)
        T = samp_rate_s / (2 * len(k))
        freq_label = k * T

        for i in range(batch.shape[0]):
            # Look at FFT
            plt.plot(freq_label, batch[i, :, 0, 0])
            plt.plot(freq_label, batch[i, :, 1, 0])
            plt.show()

    return batch

def debug():
    print('X: ',X)
    print('y: ',y)
    print('conv1: ',conv1)
    print('conv2: ',conv2)
    print('pool3: ',pool3)
    print('pool3flat: ',pool3_flat)
    print('fc1: ',fc1)
    print('logits: ',logits)
    print('Yprob: ',Y_prob)

# Add ops to save and restore all the variables.
saver = tf.train.Saver()

num_epochs = 20
batch_size = 10

with tf.Session() as sess:
    init.run()

    # Restore variables from disk.
    #saver.restore(sess, "/tmp/model.ckpt")
    #print("Model restored.")

    # Prints the structure of the network one layer at a time
    debug()

    train_data = Chunks(['HS_D36', 'HS_D37'], chunk_size_ms)

    test_data = Chunks(['HS_D35'], chunk_size_ms)

    # print('\n*****Testing the net (Pre training)*****')
    # for i in range(5):
    #     X_batch, y_batch = train_data.get_rand_batch(batch_size)
    #     #X_batch = get_freqs(X_batch)
    #     ev = Y_prob.eval(feed_dict={X: X_batch, y: y_batch})
    #     batch_mse = mse.eval(feed_dict={X: X_batch, y: y_batch})
    #     print(ev, batch_mse)

    print('\n*****Training the net*****')
    for epoch in range(num_epochs):
        for i in range(batch_size):
            step = epoch * batch_size + i
            X_batch, y_batch = train_data.get_rand_batch(batch_size)
            #X_batch = get_freqs(X_batch)
            if i % 10 == 0:
                summary_str = mse_summary.eval(feed_dict={X:X_batch,y:y_batch})
                file_write.add_summary(summary_str,step)
            sess.run(training_op, feed_dict={X: X_batch, y: y_batch})
        acc_train = mse.eval(feed_dict={X: X_batch, y: y_batch})

        X_test, y_test = test_data.get_rand_batch(batch_size)
        #X_test = get_freqs(X_test)

        acc_test = mse.eval(feed_dict={X: X_test, y: y_test})
        print(epoch, "Train MSE:", acc_train, "Test MSE:", acc_test)

        #if epoch % 5 == 0:
        #    # Save the variables to disk.
        #    save_path = saver.save(sess, "/tmp/model.ckpt")
        #    print("Model saved in file: %s" % save_path)

    # print('\n*****Testing the net (Post training)*****')
    # for i in range(2):
    #     X_batch, y_batch = train_data.get_rand_batch(batch_size)
    #     #X_batch = get_freqs(X_batch)
    #     ev = Y_prob.eval(feed_dict={X: X_batch, y: y_batch})
    #     batch_mse = mse.eval(feed_dict={X: X_batch, y: y_batch})
    #     print(ev, batch_mse)
    

    ## Save the variables to disk.
    #save_path = saver.save(sess, "/tmp/model.ckpt")
    #print("Model saved in file: %s" % save_path)