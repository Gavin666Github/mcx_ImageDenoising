import time
from utils import *
import tensorflow as tf


def dncnn(input, is_training=True, output_channels=1):
    with tf.variable_scope('block1'):
        output = tf.layers.conv2d(
            input, 128, 3, padding='same', activation=tf.nn.relu)
    for layers in xrange(2, 16 + 1):
        with tf.variable_scope('block%d' % layers):
            output = tf.layers.conv2d(
                output, 128, 3, padding='same', name='conv%d' %
                layers, use_bias=False)
            output = tf.nn.relu(
                tf.layers.batch_normalization(
                    output, training=is_training))
    with tf.variable_scope('block17'):
        output = tf.layers.conv2d(output, output_channels, 3, padding='same')

    return input - output


class denoiser(object):
    def __init__(self, sess, input_c_dim=1, batch_size=64):
        self.sess = sess
        self.input_c_dim = input_c_dim

        # build model
        self.X = tf.placeholder(
            tf.float32, [
                None, None, None, self.input_c_dim], name='noisy_image')
        self.Y_ = tf.placeholder(
            tf.float32, [
                None, None, None, self.input_c_dim], name='clean_image')

        self.is_training = tf.placeholder(tf.bool, name='is_training')

        self.Y = dncnn(self.X, is_training=self.is_training)  # trained output

        self.loss = (1.0 / batch_size) * tf.nn.l2_loss(self.Y_ - self.Y)

        self.lr = tf.placeholder(tf.float32, name='learning_rate')

        optimizer = tf.train.AdamOptimizer(self.lr, name='AdamOptimizer')

        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)

        with tf.control_dependencies(update_ops):
            self.train_op = optimizer.minimize(self.loss)

        init = tf.global_variables_initializer()
        self.sess.run(init)
        print("[*] Initialize model successfully...")

    def load(self, checkpoint_dir):
        '''
        read checkpoint
        '''
        print("[*] Reading checkpoint...")
        saver = tf.train.Saver()
        ckpt = tf.train.get_checkpoint_state(checkpoint_dir)
        if ckpt and ckpt.model_checkpoint_path:
            full_path = tf.train.latest_checkpoint(checkpoint_dir)
            global_step = int(full_path.split('/')[-1].split('-')[-1])
            saver.restore(self.sess, full_path)
            return True, global_step
        else:
            return False, 0

    def train(self, noisy_data, clean_data, batch_size,
              ckpt_dir, epoch, lr, eval_every_epoch=2):
        # assert data range is between 0 and 1
        numBatch = int(noisy_data.shape[0] / batch_size)

        #-----------------------
        # load pretrained model
        #-----------------------
        load_model_status, global_step = self.load(ckpt_dir)
        if load_model_status:
            iter_num = global_step
            start_epoch = global_step // numBatch
            start_step = global_step % numBatch
            print("[*] Model restore success!")
        else:
            iter_num = 0
            start_epoch = 0
            start_step = 0
            print("[*] Not find pretrained model!")

        # make summary
        tf.summary.scalar('loss', self.loss)
        tf.summary.scalar('lr', self.lr)
        writer = tf.summary.FileWriter('./logs', self.sess.graph)
        merged = tf.summary.merge_all()

        print(
            "[*] Start training, with start epoch %d start iter %d : " %
            (start_epoch, iter_num))

        start_time = time.time()

        samples = noisy_data.shape[0]

        for epoch in xrange(start_epoch, epoch):
            # randomize data
            row_idx = np.arange(samples)
            np.random.shuffle(row_idx)

            noisy_input = noisy_data[row_idx, :]
            clean_input = clean_data[row_idx, :]
            # print noisy_new.shape, clean_new.shape

            for batch_id in xrange(start_step, numBatch):
                batch_noisy = noisy_input[batch_id *
                                          batch_size:(batch_id +
                                                      1) *
                                          batch_size, :, :, :]
                batch_clean = clean_input[batch_id *
                                          batch_size:(batch_id +
                                                      1) *
                                          batch_size, :, :, :]

                _, loss, summary = self.sess.run([self.train_op, self.loss, merged],
                                                 feed_dict={self.X: batch_noisy,
                                                            self.Y_: batch_clean,
                                                            self.lr: lr[epoch],
                                                            self.is_training: True})

                print("Epoch: [%2d] [%4d/%4d] time: %4.4f, loss: %.6f"
                      % (epoch + 1, batch_id + 1, numBatch, time.time() - start_time, loss))

                iter_num += 1
                #writer.add_summary(summary, iter_num)

            if np.mod(epoch + 1, eval_every_epoch) == 0:
                # self.evaluate(iter_num, eval_data,
                # summary_merged=summary_psnr, summary_writer=writer)  #
                # eval_data value range is 0-255
                self.save(iter_num, ckpt_dir)

        print("[*] Finish training.")

    def save(self, iter_num, ckpt_dir, model_name='DnCNN-tensorflow'):
        saver = tf.train.Saver()
        checkpoint_dir = ckpt_dir
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)
        print("[*] Saving model...")
        saver.save(self.sess,
                   os.path.join(checkpoint_dir, model_name),
                   global_step=iter_num)
