""" TF Code Corrector Implementation """
import tensorflow as tf
import numpy as np
import random
import os
import sys

from models.train_model import TrainModel
from models.evaluation_model import EvaluationModel

tf.app.flags.DEFINE_string("data_directory", "", "Directory of the data set")
tf.app.flags.DEFINE_string("output_directory", "", "Output directory for checkpoints and tests")
tf.app.flags.DEFINE_string("checkpoint", "", "Checkpoint to evaluate. If none is given, the latest one is chosen.")
tf.app.flags.DEFINE_integer("pad_id", 1, "Code of padding character")
tf.app.flags.DEFINE_integer("sos_id", 2, "Code of start-of-sequence character")
tf.app.flags.DEFINE_integer("eos_id", 3, "Code of end-of-sequence character")
tf.app.flags.DEFINE_integer("batch_size", 32, "Batch size for training input")
tf.app.flags.DEFINE_integer("num_layers", 4, "Number of layers of the network")
tf.app.flags.DEFINE_integer("num_units", 256, "Number of units in each layer")
tf.app.flags.DEFINE_integer("num_iterations", 12000, "Number of iterations in training")
tf.app.flags.DEFINE_float("max_gradient_norm", 5.0, "Clip gradients to this norm")
tf.app.flags.DEFINE_float("learning_rate", 0.001, "Learning rate for the optimizer")
tf.app.flags.DEFINE_boolean("use_attention", True, "Wheter to use an attention mechansim")
tf.app.flags.DEFINE_boolean("reverse_input", False, "Wheter to reverse the input sequence")
tf.app.flags.DEFINE_string("cell_type", "lstm", "Cell type for the encoder and decoder")

FLAGS = tf.app.flags.FLAGS

def main(_):
    test_files = [ os.path.join(FLAGS.data_directory, 'test_files', file)
                    for file in os.listdir(os.path.join(FLAGS.data_directory, 'test_files'))
                    if file.endswith('.src')]


    eval_graph = tf.Graph()

    with eval_graph.as_default():
        eval_iterator, eval_file = create_iterator()
        eval_model = EvaluationModel(FLAGS, eval_iterator)

    eval_sess = tf.Session(graph=eval_graph)

    if FLAGS.checkpoint:
        print("load from checkpoint {}".format(FLAGS.checkpoint))
        restore_path = FLAGS.checkpoint
    else:
        print("load from latest checkpoint")
        restore_path = tf.train.latest_checkpoint(FLAGS.output_directory)
    eval_model.saver.restore(eval_sess, restore_path)

    for file in test_files:
        file_name = os.path.split(file)[1].split('.')[0]
        print("evaluating {}".format(file_name))
        sys.stdout.flush()
        eval_sess.run(eval_iterator.initializer, feed_dict={eval_file: file})
        with open(os.path.join(FLAGS.output_directory, file_name + '.java'), 'w') as translation_file:
            while(True):
                try:
                    translations = eval_model.eval(eval_sess, silent=True)
                    for t in translations:
                        s = ''
                        for c in t:
                            if c == FLAGS.eos_id:
                                break
                            s += chr(c)
                        translation_file.write(s + "\n")
                except tf.errors.OutOfRangeError:
                    break

    target_files = [ os.path.join(FLAGS.data_directory, 'test_files', file)
                    for file in os.listdir(os.path.join(FLAGS.data_directory, 'test_files'))
                    if file.endswith('.tgt')]
    print('evaluating performance')
    sys.stdout.flush()
    with open(os.path.join(FLAGS.output_directory, 'performance.txt'), 'w') as performance_file:
        for file in target_files:
            line_count = 0
            correct_count = 0
            file_name = os.path.split(file)[1].split('.')[0]
            with open(file, 'r') as target_file, \
                    open(os.path.join(FLAGS.output_directory, file_name + '.java'), 'r') as translation_file:
                while True:
                    target = target_file.readline()
                    translation = translation_file.readline()
                    if not target or not translation:
                        break
                    line_count += 1
                    if target == translation:
                        correct_count += 1
                result = "{}: {}/{}, {:.2f}%".format(file_name, correct_count, line_count, (correct_count / float(line_count) * 100))
                print(result)
                sys.stdout.flush()
                performance_file.write(result)
                performance_file.write("\n")

def create_iterator():
    java_file = tf.placeholder(tf.string, shape=[])

    def map_function(line):
        t = tf.py_func(lambda string: string.strip(), [line], tf.string)
        t = tf.map_fn(lambda elem:
                tf.py_func(lambda char: np.array(ord(char), dtype=np.int32), [elem], tf.int32), tf.string_split([t], '').values, tf.int32)
        dec_inp = tf.concat([[FLAGS.sos_id], t], 0)
        dec_out = tf.concat([t, [FLAGS.eos_id]], 0)
        return t, tf.expand_dims(tf.size(t), 0), dec_inp, dec_out, tf.expand_dims(tf.size(dec_inp),0)


    with tf.device('/cpu:0'):
        dataset = tf.data.TextLineDataset(java_file)
        dataset = dataset.map(map_function, num_parallel_calls = 4)
        pad = tf.constant(FLAGS.pad_id, dtype=tf.int32)
        dataset = dataset.apply(tf.contrib.data.padded_batch_and_drop_remainder(
                                    FLAGS.batch_size,
                                    padded_shapes=([None], [1], [None], [None], [1]),
                                    padding_values=(pad, tf.constant(0, dtype=tf.int32), pad, pad, tf.constant(0, dtype=tf.int32))))
        dataset = dataset.prefetch(FLAGS.batch_size)
        return dataset.make_initializable_iterator(), java_file


if __name__ == "__main__":
    tf.app.run()
