"""Evaluation Model"""
import tensorflow as tf

from batch_generators.java_batch_generator import JavaBatchGenerator

class EvaluationModel:

    def __init__(self, FLAGS):

        encoder_input = tf.placeholder(tf.int32, shape=(FLAGS.batch_size, None), name='encoder_input')
        sequence_lengths = tf.placeholder(tf.int32, shape=(FLAGS.batch_size), name='sequence_lengths')
        decoder_input = tf.placeholder(tf.int32, shape=(FLAGS.batch_size, None), name='decoder_input')
        target_output = tf.placeholder(tf.int32, shape=(FLAGS.batch_size, None), name='target_output')
        target_lengths = tf.placeholder(tf.int32, shape=(FLAGS.batch_size), name="target_lengths")

        if FLAGS.batch_generator == "Java":
            self.batch_generator = JavaBatchGenerator(FLAGS.data_directory).train_batch_generator(FLAGS.batch_size)
        elif FLAGS.batch_generator == "Text":
            raise NotImplementedError("TextBatchGenerator is not implemented yet")
        else:
            raise ValueError("batch_generator argument not recognized; must be one of: "
                             "Java, Text")

        # Embedding
        embedding = tf.get_variable("embedding", [256, 10], dtype=tf.float32)
        encoder_emb_inp = tf.nn.embedding_lookup(embedding, encoder_input)
        decoder_emb_inp = tf.nn.embedding_lookup(embedding, decoder_input)

        projection_layer = tf.layers.Dense(256, use_bias = False) # 256 characters can be represented in UTF-8

        encoder_layers = [tf.nn.rnn_cell.LSTMCell(FLAGS.num_units) for i in range(FLAGS.num_layers)]
        encoder_cell = tf.nn.rnn_cell.MultiRNNCell(encoder_layers)
        encoder_outputs, encoder_state = tf.nn.dynamic_rnn(cell = encoder_cell,
                                                            inputs = encoder_emb_inp,
                                                            sequence_length = sequence_lengths,
                                                            dtype = tf.float32)

        decoder_layers = [tf.nn.rnn_cell.LSTMCell(FLAGS.num_units) for i in range(FLAGS.num_layers)]
        decoder_cell = tf.nn.rnn_cell.MultiRNNCell(decoder_layers)

        # Helper
        tgt_sos_id = 2
        tgt_eos_id = 3
        helper = tf.contrib.seq2seq.GreedyEmbeddingHelper(
            embedding,
            tf.fill([FLAGS.batch_size], tgt_sos_id), tgt_eos_id)

        # Decoder
        decoder = tf.contrib.seq2seq.BasicDecoder(
            decoder_cell, helper, encoder_state,
            output_layer=projection_layer)
        # Dynamic decoding
        maximum_iterations = tf.round(tf.reduce_max(sequence_lengths) * 2)
        outputs, _, _ = tf.contrib.seq2seq.dynamic_decode(decoder, maximum_iterations = maximum_iterations)
        self.translations = outputs.sample_id

        self.encoder_input = encoder_input
        self.sequence_lengths = sequence_lengths
        self.decoder_input = decoder_input
        self.target_output = target_output
        self.target_lengths = target_lengths

        self.saver = tf.train.Saver()

    def eval(self, session):
        encoder_input, sequence_lengths, decoder_input, target_output, target_lengths = self.batch_generator.next()
        translations = session.run(self.translations,
                            feed_dict = {
                                self.encoder_input: encoder_input,
                                self.sequence_lengths: sequence_lengths,
                                self.decoder_input: decoder_input,
                                self.target_output: target_output,
                                self.target_lengths: target_lengths
                            })
        s = ''
        for c in target_output[0]:
            s += chr(c)
        print("Target: {}".format(s))
        s = ''
        for c in translations[0]:
            s += chr(c)
        print("Actual: {}".format(s))