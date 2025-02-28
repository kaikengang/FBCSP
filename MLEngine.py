import numpy as np
import scipy.signal as signal
from scipy.signal import cheb2ord
from .FBCSP import FBCSP
from .Classifier import Classifier, FeatureSelect
from . import LoadData
from sklearn.svm import SVR
from . import Preprocess

from sklearn import metrics
from sklearn.metrics import f1_score, cohen_kappa_score
import matplotlib.pyplot as plt
import seaborn as sns

class MLEngine:
    def __init__(self,ntimes=1,kfold=2,m_filters=2,window_details={},v_method='kfold',fsselect=True,sssplit=None,best=False):
        #self.sessions = sessions
        self.kfold = kfold
        self.fsselect=fsselect
        self.ntimes=ntimes
        self.window_details = window_details
        self.m_filters = m_filters
        self.sssplit = sssplit
        self.best = False
        self.v_method = v_method        

    def experiment(self, eeg_data, ssplit=None):

        '''for BCIC Dataset'''
        
        #if (self.file_to_load.find('T')!=-1):        
        #    bcic_data = LoadData.LoadBCIC(self.file_to_load, self.data_path)
        #else:
        #    bcic_data = LoadData.LoadBCICE(self.file_to_load, self.data_path)
            
        #eeg_data = bcic_data.get_epochs()
        
        '''for KU dataset'''
        # ku_data = LoadData.LoadKU(self.subject_id,self.data_path)
        # eeg_data = ku_data.get_epochs(self.sessions)
        # preprocess = Preprocess.PreprocessKU()
        # eeg_data_selected_channels = preprocess.select_channels(eeg_data.get('x_data'),eeg_data.get('ch_names'))
        # eeg_data.update({'x_data':eeg_data_selected_channels})

        fbank = FilterBank(eeg_data.get('fs'))
        fbank_coeff = fbank.get_filter_coeff()
        filtered_data = fbank.filter_data(eeg_data.get('x_data'),self.window_details)
        y_labels = eeg_data.get('y_labels')
        
        training_accuracy = []
        testing_accuracy = []
        training_kappa = []
        testing_kappa = []
        training_f1 = []
        testing_f1 = []
        for k in range(self.ntimes):
            if self.v_method == "kfold":
              '''for N times x K fold CV'''
              train_indices, test_indices = self.cross_validate_Ntimes_Kfold(y_labels,ifold=k)
            elif self.v_method == "ss":
              '''Session-to-session transfer'''
              train_indices, test_indices = self.session_to_session_split(y_labels)
            elif self.v_method == "kfolds":
              '''for K fold CV by sequential splitting'''
              train_indices, test_indices = self.cross_validate_sequential_split(y_labels)
            elif self.v_method == "hh":
              '''for one fold in half half split'''
              train_indices, test_indices = self.cross_validate_half_split(y_labels)            
            
            for i in range(self.kfold):
                train_idx = train_indices.get(i)
                test_idx = test_indices.get(i)
                print(f'Times {k+1}, Fold {i+1}: ', end = '')
                y_train, y_test = self.split_ydata(y_labels, train_idx, test_idx)
                x_train_fb, x_test_fb = self.split_xdata(filtered_data, train_idx, test_idx)

                y_classes_unique = np.unique(y_train)
                n_classes = len(np.unique(y_train))

                fbcsp = FBCSP(self.m_filters)
                fbcsp.fit(x_train_fb,y_train)
                y_train_predicted = np.zeros((y_train.shape[0], n_classes), dtype=np.float)
                y_test_predicted = np.zeros((y_test.shape[0], n_classes), dtype=np.float)

                for j in range(n_classes):
                    cls_of_interest = y_classes_unique[j]
                    select_class_labels = lambda cls, y_labels: [0 if y == cls else 1 for y in y_labels]

                    y_train_cls = np.asarray(select_class_labels(cls_of_interest, y_train))
                    y_test_cls = np.asarray(select_class_labels(cls_of_interest, y_test))

                    x_features_train = fbcsp.transform(x_train_fb,class_idx=cls_of_interest)
                    x_features_test = fbcsp.transform(x_test_fb,class_idx=cls_of_interest)

                    classifier_type = SVR(gamma='auto')
                    classifier = Classifier(classifier_type, fsselect=self.fsselect)
                    y_train_predicted[:,j] = classifier.fit(x_features_train,np.asarray(y_train_cls,dtype=np.float))
                    y_test_predicted[:,j] = classifier.predict(x_features_test)


                y_train_predicted_multi = self.get_multi_class_regressed(y_train_predicted)
                y_test_predicted_multi = self.get_multi_class_regressed(y_test_predicted)

                tr_acc =np.sum(y_train_predicted_multi == y_train, dtype=np.float) / len(y_train)
                te_acc =np.sum(y_test_predicted_multi == y_test, dtype=np.float) / len(y_test)

                #print('*'*10,'\n')
                #print(f'y_test_predicted_multi\n{str(y_test_predicted_multi)}\n')
                #print(f'y_test\n{str(y_test)}\n')
                #print('*'*10,'\n')
                
                #print(metrics.classification_report(list(y_test), y_test_predicted_multi))
                #mat = confusion_matrix(y_test, y_test_predicted_multi)
                # print(mat)
                
                
                kappa_train = cohen_kappa_score(y_train, y_train_predicted_multi)
                f1_train = f1_score(y_train, y_train_predicted_multi, average='macro')
                
                kappa_test = cohen_kappa_score(y_test, y_test_predicted_multi)
                f1_test = f1_score(y_test, y_test_predicted_multi, average='macro')
                #print(kappa)
                
                
                #print(f'y_train_predicted_multi = {str(np.sum(y_train_predicted_multi == y_train, dtype=np.float))}\n')
                #print(f'y_train_predicted_multi = {str(np.sum(y_test_predicted_multi == y_test, dtype=np.float))}\n')
                #print(f'y_train = {str(len(y_train))}\n')
                #print(f'y_test = {str(len(y_test))}\n')
                
                print(f'Train Acc = {tr_acc:.3f}, Kappa = {kappa_train:.3f}, F1 = {f1_train:.3f}; Test Acc = {te_acc:.3f}, Kappa = {kappa_test:.3f} F1 Score = {f1_test:.3f}')

                training_accuracy.append(tr_acc)
                testing_accuracy.append(te_acc)
                training_kappa.append(kappa_train)
                testing_kappa.append(kappa_test)
                training_f1.append(f1_train)
                testing_f1.append(f1_test)

        mean_training_accuracy = np.mean(np.asarray(training_accuracy))
        mean_testing_accuracy = np.mean(np.asarray(testing_accuracy))
        mean_training_kappa = np.mean(np.asarray(training_kappa))
        mean_testing_kappa = np.mean(np.asarray(testing_kappa))
        mean_training_f1 = np.mean(np.asarray(training_f1))
        mean_testing_f1 = np.mean(np.asarray(testing_f1))
        
        std_training_accuracy = np.std(np.asarray(training_accuracy))
        std_testing_accuracy = np.std(np.asarray(testing_accuracy))
        std_training_kappa = np.std(np.asarray(training_kappa))
        std_testing_kappa = np.std(np.asarray(testing_kappa))
        std_training_f1 = np.std(np.asarray(training_f1))
        std_testing_f1 = np.std(np.asarray(testing_f1))
        
        if self.best:
          best_training_accuracy = np.max(np.asarray(training_accuracy))
          best_testing_accuracy = np.max(np.asarray(testing_accuracy))
          best_training_kappa = np.max(np.asarray(training_kappa))
          best_testing_kappa = np.max(np.asarray(testing_kappa))
          best_training_f1 = np.max(np.asarray(training_f1))
          best_testing_f1 = np.max(np.asarray(testing_f1))
    
        print('*'*10)
        print(f'Mean Train Acc = {mean_training_accuracy:.3f}',u'\u00B1',f'{std_training_accuracy:.3f}, Kappa = {mean_training_kappa:.3f}',u'\u00B1',f'{std_training_kappa:.3f}, F1 = {mean_training_f1:.3f}',u'\u00B1',f'{std_training_f1:.3f}')
        print(f'Mean Test Acc = {mean_testing_accuracy:.3f}',u'\u00B1',f'{std_testing_accuracy:.3f}, Kappa = {mean_testing_kappa:.3f}',u'\u00B1',f'{std_testing_kappa:.3f}, F1 = {mean_testing_f1:.3f}',u'\u00B1',f'{std_testing_f1:.3f}')
        print('*'*10)
        
        evalScore = dict()
        
        evalScore['mean_training_accuracy'] = mean_training_accuracy
        evalScore['std_training_accuracy'] = std_training_accuracy
        if self.best: evalScore['best_training_accuracy'] = best_training_accuracy
        evalScore['mean_training_kappa'] = mean_training_kappa
        evalScore['std_training_kappa'] = std_training_kappa
        if self.best: evalScore['best_training_kappa'] = best_training_kappa
        evalScore['mean_training_f1'] = mean_training_f1
        evalScore['std_training_f1'] = std_training_f1
        if self.best: evalScore['best_training_f1'] = best_training_f1
        evalScore['mean_testing_accuracy'] = mean_testing_accuracy
        evalScore['std_testing_accuracy'] = std_testing_accuracy
        if self.best: evalScore['best_testing_accuracy'] = best_testing_accuracy
        evalScore['mean_testing_kappa'] = mean_testing_kappa
        evalScore['std_testing_kappa'] = std_testing_kappa
        if self.best: evalScore['best_testing_kappa'] = best_testing_kappa
        evalScore['mean_testing_f1'] = mean_testing_f1
        evalScore['std_testing_f1'] = std_testing_f1
        if self.best: evalScore['best_testing_f1'] = best_testing_f1
        
        return evalScore

    def cross_validate_Ntimes_Kfold(self, y_labels, ifold=0):
        from sklearn.model_selection import StratifiedKFold
        train_indices = {}
        test_indices = {}
        random_seed = ifold
        skf_model = StratifiedKFold(n_splits=self.kfold, shuffle=True, random_state=random_seed)
        i = 0
        for train_idx, test_idx in skf_model.split(np.zeros(len(y_labels)), y_labels):
            train_indices.update({i: train_idx})
            test_indices.update({i: test_idx})
            i += 1
        return train_indices, test_indices

    def cross_validate_sequential_split(self, y_labels):
        from sklearn.model_selection import StratifiedKFold
        train_indices = {}
        test_indices = {}
        skf_model = StratifiedKFold(n_splits=self.kfold, shuffle=False)
        i = 0
        for train_idx, test_idx in skf_model.split(np.zeros(len(y_labels)), y_labels):
            train_indices.update({i: train_idx})
            test_indices.update({i: test_idx})
            i += 1
        return train_indices, test_indices

    def cross_validate_half_split(self, y_labels):
        import math
        unique_classes = np.unique(y_labels)
        all_labels = np.arange(len(y_labels))
        train_idx =np.array([])
        test_idx = np.array([])
        for cls in unique_classes:
            cls_indx = all_labels[np.where(y_labels==cls)]
            if len(train_idx)==0:
                train_idx = cls_indx[:math.ceil(len(cls_indx)/2)]
                test_idx = cls_indx[math.ceil(len(cls_indx)/2):]
            else:
                train_idx=np.append(train_idx,cls_indx[:math.ceil(len(cls_indx)/2)])
                test_idx=np.append(test_idx,cls_indx[math.ceil(len(cls_indx)/2):])

        train_indices = {0:train_idx}
        test_indices = {0:test_idx}

        return train_indices, test_indices

    def session_to_session_split(self, y_labels):        
        all_labels = len(y_labels)
       
        train_indices = {}
        test_indices = {}
        train_idx = range(0,self.sssplit)
        test_idx = range(self.sssplit+1,all_labels)

        train_indices = {0:train_idx}
        test_indices = {0:test_idx}

        return train_indices, test_indices        

    def split_xdata(self,eeg_data, train_idx, test_idx):
        x_train_fb=np.copy(eeg_data[:,train_idx,:,:])
        x_test_fb=np.copy(eeg_data[:,test_idx,:,:])
        return x_train_fb, x_test_fb

    def split_ydata(self,y_true, train_idx, test_idx):
        y_train = np.copy(y_true[train_idx])
        y_test = np.copy(y_true[test_idx])

        return y_train, y_test

    def get_multi_class_label(self,y_predicted, cls_interest=0):
        y_predict_multi = np.zeros((y_predicted.shape[0]))
        for i in range(y_predicted.shape[0]):
            y_lab = y_predicted[i, :]
            lab_pos = np.where(y_lab == cls_interest)[0]
            if len(lab_pos) == 1:
                y_predict_multi[i] = lab_pos
            elif len(lab_pos > 1):
                y_predict_multi[i] = lab_pos[0]
        return y_predict_multi

    def get_multi_class_regressed(self, y_predicted):
        y_predict_multi = np.asarray([np.argmin(y_predicted[i,:]) for i in range(y_predicted.shape[0])])
        return y_predict_multi

def SummarizeResults(evalScore):
  import pandas as pd

  # Map the results to a pandas dataframe
  df = pd.DataFrame(evalScore)

  # You can check what each columns refer to 
  #print(df.columns)

  # Rename the columns for better visualization
  columns = [('Train','Acc'),('Train','AStd'),('Train','Kappa'),('Train','KStd'),('Train','F1'),('Train','FStd'),
            ('Test','Acc'),('Test','AStd'),('Test','Kappa'),('Test','KStd'),('Test','F1'),('Test','FStd')]
  df.columns=pd.MultiIndex.from_tuples(columns)

  # Instead of subjects 0 to 8, add 1 to display 1 to 9
  df.index = np.arange(1, len(df)+1)

  # Compute the average across subjects
  df.loc['Average'] = df.mean()

  # Can use the below applymap to apply to all columns
  #df=df.applymap('{0:.3f}'.format)            

  # Alternatively, can use below to apply to individual columns
  df[('Train','Acc')]=df[('Train','Acc')].apply('{0:.3f}'.format)            
  df[('Train','AStd')]=df[('Train','AStd')].apply('\u00B1{0:.3f}'.format)            
  df[('Train','Kappa')]=df[('Train','Kappa')].apply('{0:.3f}'.format)            
  df[('Train','KStd')]=df[('Train','KStd')].apply('\u00B1{0:.3f}'.format)            
  df[('Train','F1')]=df[('Train','F1')].apply('{0:.3f}'.format)            
  df[('Train','FStd')]=df[('Train','FStd')].apply('\u00B1{0:.3f}'.format)            
  df[('Test','Acc')]=df[('Test','Acc')].apply('{0:.3f}'.format)            
  df[('Test','AStd')]=df[('Test','AStd')].apply('\u00B1{0:.3f}'.format)            
  df[('Test','Kappa')]=df[('Test','Kappa')].apply('{0:.3f}'.format)            
  df[('Test','KStd')]=df[('Test','KStd')].apply('\u00B1{0:.3f}'.format)            
  df[('Test','F1')]=df[('Test','F1')].apply('{0:.3f}'.format)            
  df[('Test','FStd')]=df[('Test','FStd')].apply('\u00B1{0:.3f}'.format)            

  # Format the Pandas dataframe and by drawing some borders. This will requires some knowledge on html table format
  df=df.style.set_table_styles([{'selector':'','props':'border-top: 2px solid black'},
                              {'selector':'','props':'border-bottom: 2px solid black'},                           
                              {'selector':'th','props':'text-align: center'},
                              {'selector':'th.col_heading','props':'border-top: 1px solid black'},
                              {'selector':'td','props':'text-align: right'},
                              {'selector':'.row0','props':'border-top: 2px solid black'},
                              {'selector':'.row8','props':'border-bottom: 2px solid black'},
                              {'selector':'.col5','props':'border-right: 1px solid black'}],
                              )
  return df
    
class FilterBank:
    def __init__(self,fs):
        self.fs = fs
        self.f_trans = 2
        self.f_pass = np.arange(4,40,4)
        self.f_width = 4
        self.gpass = 3
        self.gstop = 30
        self.filter_coeff={}

    def get_filter_coeff(self):
        Nyquist_freq = self.fs/2

        for i, f_low_pass in enumerate(self.f_pass):
            f_pass = np.asarray([f_low_pass, f_low_pass+self.f_width])
            f_stop = np.asarray([f_pass[0]-self.f_trans, f_pass[1]+self.f_trans])
            wp = f_pass/Nyquist_freq
            ws = f_stop/Nyquist_freq
            order, wn = cheb2ord(wp, ws, self.gpass, self.gstop)
            b, a = signal.cheby2(order, self.gstop, ws, btype='bandpass')
            self.filter_coeff.update({i:{'b':b,'a':a}})

        return self.filter_coeff

    def filter_data(self,eeg_data,window_details={}):
        n_trials, n_channels, n_samples = eeg_data.shape
        if window_details:
            n_samples = int(self.fs*(window_details.get('tmax')-window_details.get('tmin')))+1
        filtered_data=np.zeros((len(self.filter_coeff),n_trials,n_channels,n_samples))
        for i, fb in self.filter_coeff.items():
            b = fb.get('b')
            a = fb.get('a')
            eeg_data_filtered = np.asarray([signal.lfilter(b,a,eeg_data[j,:,:]) for j in range(n_trials)])
            if window_details:
                eeg_data_filtered = eeg_data_filtered[:,:,int((4.5+window_details.get('tmin'))*self.fs):int((4.5+window_details.get('tmax'))*self.fs)+1]
            filtered_data[i,:,:,:]=eeg_data_filtered

        return filtered_data
