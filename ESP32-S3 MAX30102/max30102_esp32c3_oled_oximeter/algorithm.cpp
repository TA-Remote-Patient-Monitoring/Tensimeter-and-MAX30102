/** \file algorithm.cpp ******************************************************
*
* Project: MAXREFDES117#
* Filename: algorithm.cpp
* Description: This module calculates the heart rate/SpO2 level
*/

#include "algorithm.h"
#include "Arduino.h"

void maxim_heart_rate_and_oxygen_saturation(uint32_t *pun_ir_buffer, int32_t n_ir_buffer_length, uint32_t *pun_red_buffer, float *pn_spo2, int8_t *pch_spo2_valid, 
                int32_t *pn_heart_rate, int8_t *pch_hr_valid)
{
  uint32_t un_ir_mean;
  int32_t k, n_i_ratio_count;
  int32_t i, n_exact_ir_valley_locs_count, n_middle_idx;
  int32_t n_th1, n_npks;   
  int32_t an_ir_valley_locs[15] ;
  int32_t n_peak_interval_sum;
  static int32_t n_last_peak_interval=FS;
  
  int32_t n_y_ac, n_x_ac;
  int32_t n_y_dc_max, n_x_dc_max; 
  int32_t n_y_dc_max_idx, n_x_dc_max_idx; 
  int32_t an_ratio[5], n_ratio_average; 
  int32_t n_nume, n_denom ;
  int32_t an_x[BUFFER_SIZE];
  int32_t an_y[BUFFER_SIZE];

  un_ir_mean =0; 
  for (k=0 ; k<n_ir_buffer_length ; k++ ) un_ir_mean += pun_ir_buffer[k] ;
  un_ir_mean =un_ir_mean/n_ir_buffer_length ;
  
  for (k=0 ; k<n_ir_buffer_length ; k++ )  
    an_x[k] = un_ir_mean - pun_ir_buffer[k] ; 

  for(k=0; k< BUFFER_SIZE_MA4; k++){
    an_x[k]=( an_x[k]+an_x[k+1]+ an_x[k+2]+ an_x[k+3])/(int)4;        
  }
  n_th1=0; 
  for ( k=0 ; k<BUFFER_SIZE_MA4 ;k++){
    n_th1 +=  an_x[k];
  }
  n_th1= n_th1/ (BUFFER_SIZE_MA4);
  if( n_th1<30) n_th1=30;
  if( n_th1>60) n_th1=60;

  for ( k=0 ; k<15;k++) an_ir_valley_locs[k]=0;
  maxim_find_peaks( an_ir_valley_locs, &n_npks, an_x, BUFFER_SIZE_MA4, n_th1, 4, 15 );
  n_peak_interval_sum =0;
  if (n_npks>=2){
    for (k=1; k<n_npks; k++) n_peak_interval_sum += (an_ir_valley_locs[k] - an_ir_valley_locs[k -1] ) ;
    n_peak_interval_sum =n_peak_interval_sum/(n_npks-1);
    *pn_heart_rate =(int32_t)( (FS*60)/ n_peak_interval_sum );
    *pch_hr_valid  = 1;
  }
  else  { 
    *pn_heart_rate = -999;
    *pch_hr_valid  = 0;
  }

  for (k=0 ; k<n_ir_buffer_length ; k++ )  {
      an_x[k] =  pun_ir_buffer[k] ; 
      an_y[k] =  pun_red_buffer[k] ; 
  }

  n_exact_ir_valley_locs_count = n_npks; 
  n_ratio_average =0; 
  n_i_ratio_count = 0; 
  for(k=0; k< 5; k++) an_ratio[k]=0;
  for (k=0; k< n_exact_ir_valley_locs_count; k++){
    if (an_ir_valley_locs[k] > BUFFER_SIZE ) {
      *pn_spo2 =  -999 ;
      *pch_spo2_valid  = 0; 
      return;
    }
  }
  for (k=0; k< n_exact_ir_valley_locs_count-1; k++){
    n_y_dc_max= -16777216 ; 
    n_x_dc_max= -16777216; 
    if (an_ir_valley_locs[k+1]-an_ir_valley_locs[k] >3){
        for (i=an_ir_valley_locs[k]; i< an_ir_valley_locs[k+1]; i++){
          if (an_x[i]> n_x_dc_max) {n_x_dc_max =an_x[i]; n_x_dc_max_idx=i;}
          if (an_y[i]> n_y_dc_max) {n_y_dc_max =an_y[i]; n_y_dc_max_idx=i;}
      }
      n_y_ac= (an_y[an_ir_valley_locs[k+1]] - an_y[an_ir_valley_locs[k] ] )*(n_y_dc_max_idx -an_ir_valley_locs[k]);
      n_y_ac=  an_y[an_ir_valley_locs[k]] + n_y_ac/ (an_ir_valley_locs[k+1] - an_ir_valley_locs[k])  ; 
      n_y_ac=  an_y[n_y_dc_max_idx] - n_y_ac;
      n_x_ac= (an_x[an_ir_valley_locs[k+1]] - an_x[an_ir_valley_locs[k] ] )*(n_x_dc_max_idx -an_ir_valley_locs[k]);
      n_x_ac=  an_x[an_ir_valley_locs[k]] + n_x_ac/ (an_ir_valley_locs[k+1] - an_ir_valley_locs[k]); 
      n_x_ac=  an_x[n_y_dc_max_idx] - n_x_ac;
      n_nume=( n_y_ac *n_x_dc_max)>>7;
      n_denom= ( n_x_ac *n_y_dc_max)>>7;
      if (n_denom>0  && n_i_ratio_count <5 &&  n_nume != 0)
      {   
        an_ratio[n_i_ratio_count]= (n_nume*100)/n_denom ;
        n_i_ratio_count++;
      }
    }
  }
  maxim_sort_ascend(an_ratio, n_i_ratio_count);
  n_middle_idx= n_i_ratio_count/2;

  if (n_middle_idx >1)
    n_ratio_average =( an_ratio[n_middle_idx-1] +an_ratio[n_middle_idx])/2;
  else
    n_ratio_average = an_ratio[n_middle_idx ];

  if( n_ratio_average>2 && n_ratio_average <184){
    *pn_spo2 = uch_spo2_table[n_ratio_average];
    *pch_spo2_valid  = 1;
  }
  else{
    *pn_spo2 =  -999 ;
    *pch_spo2_valid  = 0; 
  }
}

void maxim_find_peaks( int32_t *pn_locs, int32_t *n_npks,  int32_t  *pn_x, int32_t n_size, int32_t n_min_height, int32_t n_min_distance, int32_t n_max_num )
{
  maxim_peaks_above_min_height( pn_locs, n_npks, pn_x, n_size, n_min_height );
  maxim_remove_close_peaks( pn_locs, n_npks, pn_x, n_min_distance );
  *n_npks = min( *n_npks, n_max_num );
}

void maxim_peaks_above_min_height( int32_t *pn_locs, int32_t *n_npks,  int32_t  *pn_x, int32_t n_size, int32_t n_min_height )
{
  int32_t i = 1, n_width;
  *n_npks = 0;
  
  while (i < n_size-1){
    if (pn_x[i] > n_min_height && pn_x[i] > pn_x[i-1]){
      n_width = 1;
      while (i+n_width < n_size && pn_x[i] == pn_x[i+n_width])
        n_width++;
      if (pn_x[i] > pn_x[i+n_width] && (*n_npks) < 15 ) {
        pn_locs[(*n_npks)++] = i;    
        i += n_width+1;
      } else
        i += n_width;
    }
    else
      i++;
  }
}

void maxim_remove_close_peaks(int32_t *pn_locs, int32_t *pn_npks, int32_t *pn_x, int32_t n_min_distance)
{
  int32_t i, j, n_old_npks, n_dist;
  maxim_sort_indices_descend( pn_x, pn_locs, *pn_npks );

  for ( i = -1; i < *pn_npks; i++ ){
    n_old_npks = *pn_npks;
    *pn_npks = i+1;
    for ( j = i+1; j < n_old_npks; j++ ){
      n_dist =  pn_locs[j] - ( i == -1 ? -1 : pn_locs[i] );
      if ( n_dist > n_min_distance || n_dist < -n_min_distance )
        pn_locs[(*pn_npks)++] = pn_locs[j];
    }
  }

  maxim_sort_ascend( pn_locs, *pn_npks );
}

void maxim_sort_ascend(int32_t  *pn_x, int32_t n_size) 
{
  int32_t i, j, n_temp;
  for (i = 1; i < n_size; i++) {
    n_temp = pn_x[i];
    for (j = i; j > 0 && n_temp < pn_x[j-1]; j--)
        pn_x[j] = pn_x[j-1];
    pn_x[j] = n_temp;
  }
}

void maxim_sort_indices_descend(  int32_t  *pn_x, int32_t *pn_indx, int32_t n_size)
{
  int32_t i, j, n_temp;
  for (i = 1; i < n_size; i++) {
    n_temp = pn_indx[i];
    for (j = i; j > 0 && pn_x[n_temp] > pn_x[pn_indx[j-1]]; j--)
      pn_indx[j] = pn_indx[j-1];
    pn_indx[j] = n_temp;
  }
}
