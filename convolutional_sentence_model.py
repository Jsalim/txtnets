__author__ = 'mdenil'

import numpy as np
import pyprind

from cpu import model

# def stack2param(stack, decodeInfo):
#     stack = stack.ravel()
#
#     # extract
#     base = 0
#     decoded = []
#     for i,shape in enumerate(decodeInfo):
#         m = stack[base:base + np.prod(shape)].reshape(*shape, order='F')
#         base += np.prod(shape)
#         decoded.append(m)
#
#     # map to numpy shapes
#     for i in xrange(len(decoded)):
#         # I want to convolve along rows because that makes sense for C-ordered arrays
#         # the matlab code also convolves along rows, so I need to not transpose the convolution filters
#         if i not in [1]:
#             decoded[i] = np.ascontiguousarray(np.transpose(decoded[i]))
#         else:
#             decoded[i] = np.ascontiguousarray(decoded[i])
#
#     return decoded


def load_testing_model(file_name):
    model_data = scipy.io.loadmat(file_name)

    # [CR_E, CR_1, CR_1_b, CR_2, CR_2_b, CR_3, CR_3_b, CR_Z, _, _] = stack2param(model_data['X'], model_data['decodeInfo'])

    CR_E = np.ascontiguousarray(np.transpose(model_data['CR_E']))
    # I want to convolve along rows because that makes sense for C-ordered arrays
    # the matlab code also convolves along rows, so I need to not transpose the convolution filters
    CR_1 = np.ascontiguousarray(model_data['CR_1'])
    CR_1_b = np.ascontiguousarray(np.transpose(model_data['CR_1_b']))

    embedding = model.embedding.WordEmbedding(
        dimension=CR_E.shape[1],
        vocabulary_size=CR_E.shape[0])
    assert CR_E.shape == embedding.E.shape
    embedding.E = CR_E

    conv = model.transfer.SentenceConvolution(
        n_feature_maps=5,
        kernel_width=6,
        n_input_dimensions=42)
    assert conv.W.shape == CR_1.shape
    conv.W = CR_1

    bias = model.transfer.Bias(
        n_input_dims=21,
        n_feature_maps=5)
    bias.b = CR_1_b.reshape(bias.b.shape)

    csm = model.model.CSM(
        input_axes=['b', 'w'],
        layers=[
            embedding,
            conv,
            model.pooling.SumFolding(),
            model.pooling.KMaxPooling(k=4),
            bias,
            model.nonlinearity.Tanh(),
            ],
        )

    return csm


if __name__ == "__main__":
    import scipy.io

    data_file_name = "cnn-sm-gpu-kmax/SENT_vec_1_emb_ind_bin.mat"
    data = scipy.io.loadmat(data_file_name)

    embedding_dim = 42
    batch_size = 40
    vocabulary_size = int(data['size_vocab'])
    max_epochs = 1

    train = data['train'] - 1
    train_sentence_lengths = data['train_lbl'][:,1]

    max_sentence_length = data['train'].shape[1]

    csm = load_testing_model("cnn-sm-gpu-kmax/DEBUGGING_MODEL.mat")

    n_batches_per_epoch = int(data['train'].shape[0] / batch_size)

    matlab_results = scipy.io.loadmat("cnn-sm-gpu-kmax/BATCH_RESULTS_ONE_PASS_ONE_LAYER_CHECK.mat")['batch_results']

    progress_bar = pyprind.ProgPercent(n_batches_per_epoch)

    for batch_index in xrange(n_batches_per_epoch):

        # batch_index = 4065 # <- this batch is the one with errors

        minibatch = train[batch_index*batch_size:(batch_index+1)*batch_size]

        meta = {'lengths': train_sentence_lengths[batch_index*batch_size:(batch_index+1)*batch_size]}

        # s1 = csm.fprop(minibatch, num_layers=1, meta=meta)
        # s2 = csm.fprop(minibatch, num_layers=2, meta=meta)
        # s3 = csm.fprop(minibatch, num_layers=3, meta=meta)
        # s4 = csm.fprop(minibatch, num_layers=4, meta=meta)
        # s5 = csm.fprop(minibatch, num_layers=5, meta=meta)
        # s6 = csm.fprop(minibatch, num_layers=6, meta=meta)
        # assert np.allclose(s6, csm.fprop(minibatch, meta=meta))

        out = csm.fprop(minibatch, meta)

        if not np.allclose(out, matlab_results[batch_index]):
            print "\nFailed batch {}. Max abs err={}.  There are {} errors larger than 1e-2.".format(
                batch_index,
                np.max(np.abs(out - matlab_results[batch_index])),
                np.sum(np.abs(out - matlab_results[batch_index]) > 1e-2))

        progress_bar.update()



