import tensorflow as tf
import voxel
import numpy as np
from PIL import Image
import dataset
from tqdm import tqdm

n_convfilter = [96, 128, 256, 256, 256, 256]
n_deconvfilter = [128, 128, 128, 64, 32, 2]
n_gru_vox = 4
n_fc_filters = [1024]



def initialize_placeholders():
    with tf.name_scope("Placeholders"):
        X = tf.placeholder(tf.float32, shape=[1, 127, 127, 3],name = "X")
        Y = tf.placeholder(tf.float32, shape=[32, 32, 32],name = "Y")
        S = tf.placeholder(tf.float32, shape=[1,n_gru_vox,n_deconvfilter[0],n_gru_vox,n_gru_vox],name = "S")
    return X,Y,S

X,Y,S = initialize_placeholders()

with tf.name_scope("Dataset"):
    x_train = dataset.train_data()
    y_train = dataset.train_labels()
print("Finished reading dataset.")

encoder_gru_kernel_shapes = [
    #Encoder
    [7,7,3,n_convfilter[0]], #conv1a
    [3,3,n_convfilter[0],n_convfilter[0]], #conv1b
    [3,3,n_convfilter[0],n_convfilter[1]], #conv2a
    [3,3,n_convfilter[1],n_convfilter[1]], #conv2b
    [1,1,n_convfilter[0],n_convfilter[1]], #conv2c
    [3,3,n_convfilter[1],n_convfilter[2]], #conv3a
    [3,3,n_convfilter[2],n_convfilter[2]], #conv3b
    [1,1,n_convfilter[1],n_convfilter[2]], #conv3c
    [3,3,n_convfilter[2],n_convfilter[3]], #conv4a
    [3,3,n_convfilter[3],n_convfilter[3]], #conv4b
    [3,3,n_convfilter[3],n_convfilter[4]], #conv5a
    [3,3,n_convfilter[4],n_convfilter[4]], #conv5b
    [1,1,n_convfilter[4],n_convfilter[4]], #conv5c
    [3,3,n_convfilter[4],n_convfilter[5]], #conv6a
    [3,3,n_convfilter[5],n_convfilter[5]], #conv6b
    [1,n_fc_filters[0]], #fc7
    #GRU
    [1024,8192], #w_update
    [3,3,3,n_gru_vox,n_gru_vox], #update_gate
    [3,3,3,n_gru_vox,n_gru_vox], #reset_gate
    [3,3,3,n_gru_vox,n_gru_vox], #tanh_reset
    [1024,8192] #w_reset
]

decoder_kernel_shapes = [
    [3,3,3,n_deconvfilter[1],n_deconvfilter[1]], #conv7a
    [3,3,3,n_deconvfilter[1],n_deconvfilter[1]], #conv7b
    [3,3,3,n_deconvfilter[1],n_deconvfilter[2]], #conv8a
    [3,3,3,n_deconvfilter[2],n_deconvfilter[2]], #conv8b
    [3,3,3,n_deconvfilter[2],n_deconvfilter[3]], #conv9a
    [3,3,3,n_deconvfilter[3],n_deconvfilter[3]], #conv9b
    [1,1,1,n_deconvfilter[2],n_deconvfilter[3]], #conv9c
    [3,3,3,n_deconvfilter[3],n_deconvfilter[4]], #conv10a
    [3,3,3,n_deconvfilter[4],n_deconvfilter[4]], #conv10b
    [3,3,3,n_deconvfilter[4],n_deconvfilter[4]], #conv10c
    [3,3,3,n_deconvfilter[4],n_deconvfilter[5]] #conv11a
]

with tf.name_scope("encoder_gru_weights"):
    w = [tf.get_variable(
        "w"+str(_), shape=kernel, initializer = tf.glorot_normal_initializer(seed=4664), trainable=True) 
        for _,kernel in enumerate(encoder_gru_kernel_shapes)]

with tf.name_scope("decoder_weights"):
    w_decoder = [tf.get_variable(
        "w2_"+str(_), shape=kernel, initializer = tf.glorot_normal_initializer(seed=4664), trainable=True) 
        for _,kernel in enumerate(decoder_kernel_shapes)]

def test_predict(pred,ind):
    pred_name = "test_pred_"+str(ind)+".obj"
    voxel.voxel2obj(pred_name,pred)


def train(w,x_train,y_train):
    print()
    '''Do nothing'''
    for images in x_train.keys():
        ims = [] # Concatenate N images
        for image in x_train[images]:
            #image = tf.convert_to_tensor(image) # (127,127,3)
            #image = tf.reshape(image,[3,127,127])
            ims.append(image) 

        # Initial empty GRU inputs
        prev_s = tf.Variable(tf.zeros_like(
            tf.truncated_normal([1,n_gru_vox,n_deconvfilter[0],n_gru_vox,n_gru_vox], stddev=0.5)), name="prev_s")
        
        tmp = encoder(w,ims)
        tmp = gru(w,tmp,prev_s)
        tmp = decoder(w,tmp)
        l = loss(tmp,y_train[images])
        tf.summary.histogram('loss', l)



def loss(x,y):
    x = x[0,:,:,:,1]
    with tf.name_scope("loss"):
        l = tf.nn.softmax_cross_entropy_with_logits_v2(logits=x,labels=y)
    return tf.reduce_sum(l),x




def encoder_gru():
    
    with tf.name_scope("Encoder"):
        
        # Convolutional Layer #1
        conv1a = tf.nn.conv2d(input=X,filter=w[0],strides=[1,1,1,1],padding="SAME")
        conv1a = tf.nn.leaky_relu(conv1a)
        conv1b = tf.nn.conv2d(input=conv1a,filter=w[1],strides=[1,1,1,1],padding="SAME")
        conv1b = tf.nn.leaky_relu(conv1b)
        pool1 = tf.nn.max_pool(conv1b,ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="SAME")
        # [1, 64, 64, 96]

        # Convolutional Layer #2
        conv2a = tf.nn.conv2d(input=pool1,filter=w[2],strides=[1,1,1,1],padding="SAME")
        conv2a = tf.nn.leaky_relu(conv2a)
        conv2b = tf.nn.conv2d(input=conv2a,filter=w[3],strides=[1,1,1,1],padding="SAME")
        conv2b = tf.nn.leaky_relu(conv2b)
        conv2c = tf.nn.conv2d(input=pool1,filter=w[4],strides=[1,1,1,1],padding="SAME")
        conv2c = tf.nn.leaky_relu(conv2c)
        res2 = tf.add(conv2b,conv2c)
        pool2 = tf.nn.max_pool(res2,ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="VALID")
        ''' !!!TODO!!!  (1, 32, 32, 128)   ->>>      Paper result size is (1, 33, 33, 128)'''

        # Convolutional Layer #3
        conv3a = tf.nn.conv2d(input=pool2,filter=w[5],strides=[1,1,1,1],padding="SAME")
        conv3a = tf.nn.leaky_relu(conv3a)
        conv3b = tf.nn.conv2d(input=conv3a,filter=w[6],strides=[1,1,1,1],padding="SAME")
        conv3b = tf.nn.leaky_relu(conv3b)
        conv3c = tf.nn.conv2d(input=pool2,filter=w[7],strides=[1,1,1,1],padding="SAME")
        conv3c = tf.nn.leaky_relu(conv3c)
        res3 = tf.add(conv3b,conv3c)
        pool3 = tf.nn.max_pool(res3,ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="VALID")
        ''' !!!TODO!!!  (1, 16, 16, 256)   ->>>      Paper result size is (1, 17, 17, 256)'''

        # Convolutional Layer #4
        conv4a = tf.nn.conv2d(input=pool3,filter=w[8],strides=[1,1,1,1],padding="SAME")
        conv4a = tf.nn.leaky_relu(conv4a)
        conv4b = tf.nn.conv2d(input=conv4a,filter=w[9],strides=[1,1,1,1],padding="SAME")
        conv4b = tf.nn.leaky_relu(conv4b)
        pool4 = tf.nn.max_pool(conv4b,ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="SAME")
        ''' !!!TODO!!!  (1, 8, 8, 256)   ->>>      Paper result size is (1, 9, 9, 256)'''
    
        # Convolutional Layer #5
        conv5a = tf.nn.conv2d(input=pool4,filter=w[10],strides=[1,1,1,1],padding="SAME")
        conv5a = tf.nn.leaky_relu(conv5a)
        conv5b = tf.nn.conv2d(input=conv5a,filter=w[11],strides=[1,1,1,1],padding="SAME")
        conv5b = tf.nn.leaky_relu(conv5b)
        conv5c = tf.nn.conv2d(input=pool4,filter=w[12],strides=[1,1,1,1],padding="SAME")
        conv5c = tf.nn.leaky_relu(conv5c)
        res5 = tf.add(conv5b,conv5c)
        pool5 = tf.nn.max_pool(res5,ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="VALID")
        ''' !!!TODO!!!  (1, 4, 4, 256)   ->>>      Paper result size is (1, 5, 5, 256)'''
    
        # Convolutional Layer #6
        conv6a = tf.nn.conv2d(input=pool5,filter=w[13],strides=[1,1,1,1],padding="SAME")
        conv6a = tf.nn.leaky_relu(conv6a)
        conv6b = tf.nn.conv2d(input=conv6a,filter=w[14],strides=[1,1,1,1],padding="SAME")
        conv6b = tf.nn.leaky_relu(conv6b)
        pool6 = tf.nn.max_pool(conv6b,ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="SAME")
        ''' !!!TODO!!!  (1, 2, 2, 256)   ->>>      Paper result size is (1, 3, 3, 256)'''
        
        # Flatten Layer
        flat7 = tf.reshape(pool6,[pool6.shape[0],-1])
        ''' !!!TODO!!!  (1, 1024)   ->>>      Paper result size is (1, 2304)'''

        # FC Layer
        fc7 = tf.multiply(flat7,w[15])
        ''' w[15] was [1024] , now its [1,1024]. Which one is correct?'''
        # [1,1024]

    with tf.name_scope("GRU"):

        #print("Iteration no:",x_curr.shape[0])

        ''' TODO : Broadcast-dot product or matmul ??'''
        fc_layer_U = tf.matmul(fc7,w[16]) #[1,1024]x[1024,8192] // FC LAYER FOR UPDATE GATE
        fc_layer_U = tf.reshape(fc_layer_U,[-1,4,128,4,4]) #[1,4,128,4,4]

        fc_layer_R = tf.matmul(fc7,w[20]) # FC LAYER FOR RESET GATE
        fc_layer_R = tf.reshape(fc_layer_R,[-1,4,128,4,4]) #[1,4,128,4,4]
        

        update_gate = tf.nn.conv3d(S,w[17],strides=[1,1,1,1,1],padding="SAME")

        update_gate = update_gate + fc_layer_U
        update_gate = tf.sigmoid(update_gate)

        complement_update_gate = tf.subtract(tf.ones_like(update_gate),update_gate)

        reset_gate = tf.nn.conv3d(S,w[18],strides=[1,1,1,1,1],padding="SAME")
        reset_gate = reset_gate + fc_layer_R
        reset_gate = tf.sigmoid(reset_gate)

        rs = tf.multiply(reset_gate,S) # Element-wise multiply

        tanh_reset = tf.nn.conv3d(rs,w[19],strides=[1,1,1,1,1],padding="SAME")
        tanh_reset = tf.tanh(tanh_reset)

        gru_out = tf.add(
            tf.multiply(update_gate,S),
            tf.multiply(complement_update_gate,tanh_reset)
        )

    return gru_out # Return hidden state

    
    


def gru(w,x_curr, prev_s):
    
    with tf.name_scope("GRU"):
        
        x_t = x_curr[0:1,:] # -> Take a single picture out of 24 pictures

        if(x_t.shape[0]==0): # Return output if images are finished.
            return prev_s
    
        #print("Iteration no:",x_curr.shape[0])

        ''' TODO : Broadcast-dot product or matmul ??'''
        fc_layer_U = tf.matmul(x_t,w[16]) #[1,1024]x[1024,8192] // FC LAYER FOR UPDATE GATE
        fc_layer_U = tf.reshape(fc_layer_U,[-1,4,128,4,4]) #[1,4,128,4,4]

        fc_layer_R = tf.matmul(x_t,w[31]) # FC LAYER FOR RESET GATE
        fc_layer_R = tf.reshape(fc_layer_R,[-1,4,128,4,4]) #[1,4,128,4,4]
        

        update_gate = tf.nn.conv3d(prev_s,w[17],strides=[1,1,1,1,1],padding="SAME")

        update_gate = update_gate + fc_layer_U
        update_gate = tf.sigmoid(update_gate)

        complement_update_gate = tf.subtract(tf.ones_like(update_gate),update_gate)

        reset_gate = tf.nn.conv3d(prev_s,w[18],strides=[1,1,1,1,1],padding="SAME")
        reset_gate = reset_gate + fc_layer_R
        reset_gate = tf.sigmoid(reset_gate)

        rs = tf.multiply(reset_gate,prev_s) # Element-wise multiply

        tanh_reset = tf.nn.conv3d(rs,w[19],strides=[1,1,1,1,1],padding="SAME")
        tanh_reset = tf.tanh(tanh_reset)

        gru_out = tf.add(
            tf.multiply(update_gate,prev_s),
            tf.multiply(complement_update_gate,tanh_reset)
        )

    return gru(w,x_curr[1:,:],gru_out)




    
def decoder():
    
    with tf.name_scope("Decoder"):

        s = tf.transpose(S,perm=[0,1,4,3,2]) # [(1, 4, 128, 4, 4)] -> [(1, 4, 4, 4, 128)]
        unpool7 = unpool(s)

        conv7a = tf.nn.conv3d(unpool7,w_decoder[0],strides=[1,1,1,1,1],padding="SAME")
        conv7a = tf.nn.leaky_relu(conv7a)

        conv7b = tf.nn.conv3d(conv7a,w_decoder[1],strides=[1,1,1,1,1],padding="SAME")
        conv7b = tf.nn.leaky_relu(conv7b)
        res7 = tf.add(unpool7,conv7b)

        unpool8 = unpool(res7)

        conv8a = tf.nn.conv3d(unpool8,w_decoder[2],strides=[1,1,1,1,1],padding="SAME")
        conv8a = tf.nn.leaky_relu(conv8a)   

        conv8b = tf.nn.conv3d(conv8a,w_decoder[3],strides=[1,1,1,1,1],padding="SAME")
        conv8b = tf.nn.leaky_relu(conv8b)    
        res8 = tf.add(unpool8,conv8b)

        unpool9 = unpool(res8)

        conv9a = tf.nn.conv3d(unpool9,w_decoder[4],strides=[1,1,1,1,1],padding="SAME")
        conv9a = tf.nn.leaky_relu(conv9a)   

        conv9b = tf.nn.conv3d(conv9a,w_decoder[5],strides=[1,1,1,1,1],padding="SAME")
        conv9b = tf.nn.leaky_relu(conv9b)  

        conv9c = tf.nn.conv3d(unpool9,w_decoder[6],strides=[1,1,1,1,1],padding="SAME")

        res9 = tf.add(conv9c,conv9b)

        conv10a = tf.nn.conv3d(res9,w_decoder[7],strides=[1,1,1,1,1],padding="SAME")
        conv10a = tf.nn.leaky_relu(conv10a)  
        
        conv10b = tf.nn.conv3d(conv10a,w_decoder[8],strides=[1,1,1,1,1],padding="SAME")
        conv10b = tf.nn.leaky_relu(conv10b)  

        conv10c = tf.nn.conv3d(conv10a,w_decoder[9],strides=[1,1,1,1,1],padding="SAME")
        conv10c = tf.nn.leaky_relu(conv10c)  

        res10 = tf.add(conv10c,conv10b)

        conv11a = tf.nn.conv3d(res10,w_decoder[10],strides=[1,1,1,1,1],padding="SAME")
        conv11a = tf.nn.leaky_relu(conv11a)  

        conv11a = tf.contrib.layers.layer_norm(conv11a) #Norm layer

    return conv11a


def unpool(value):
    """
    :param value: A Tensor of shape [b, d0, d1, ..., dn, ch]
    :return: A Tensor of shape [b, 2*d0, 2*d1, ..., 2*dn, ch]
    """
    with tf.name_scope("Unpool"):
        sh = value.get_shape().as_list()
        dim = len(sh[1:-1])
        out = (tf.reshape(value, [-1] + sh[-dim:]))
        for i in range(dim, 0, -1):
            out = tf.concat([out, tf.zeros_like(out)], i)
        out_size = [-1] + [s * 2 for s in sh[1:-1]] + [sh[-1]]
        out = tf.reshape(out, out_size)
    return out


forward_pass = encoder_gru()

decoder_pass = decoder()

#logits = decoder_pass

# Define loss and optimizer
loss_op = loss(decoder_pass,Y)

# Calculate and clip gradients
params = tf.trainable_variables()
gradients = tf.gradients(loss_op, params)
clipped_gradients, _ = tf.clip_by_global_norm(
    gradients, tf.constant(5,name="max_gradient_norm",dtype=tf.float32)) # 1 is max_gradient_norm

# Optimization
optimizer = tf.train.AdamOptimizer(0.00001)
update_step = optimizer.apply_gradients(
    zip(clipped_gradients, params))


if __name__=="__main__":
    init = tf.global_variables_initializer()

    # Start training
    with tf.Session() as sess:

        # Run the initializer
        sess.run(init)

        # Merge all the summaries and write them out to /tmp/mnist_logs (by default)
        merged = tf.summary.merge_all()
        train_writer = tf.summary.FileWriter('./train',
                                            sess.graph)
                                            
        iter = 0
        print("Started training.")
        for image_hash in tqdm(x_train.keys()):
            iter+=1

            initial_state = tf.truncated_normal([1,n_gru_vox,n_deconvfilter[0],n_gru_vox,n_gru_vox], stddev=0.5)
            initial_state = initial_state.eval()

            for image in x_train[image_hash]:
                image = tf.convert_to_tensor(image)
                image = tf.reshape(image,[1,127,127,3])
                image = image.eval()
                initial_state = sess.run([forward_pass], feed_dict={X: image, S: initial_state})
                initial_state = np.array(initial_state[0])
            

            vox = tf.convert_to_tensor(y_train[image_hash])
            vox = vox.eval()

            _, loss = sess.run([update_step, loss_op], feed_dict={S: initial_state, Y: vox})
            print(loss[0])
            print("Object: ",iter," LOSS:  ",loss[0])
            tf.summary.histogram('loss', loss[0])
            if iter % 2 == 0:
                print("Testing Model at Iter ",iter)
                print("HASH "+image_hash)
                # Save the prediction to an OBJ file (mesh file).
                #predict(w,"test_image.png",iter)
                test_predict(loss[1],iter)
                test_predict(vox,iter+10)
        


        print("Finished!")


