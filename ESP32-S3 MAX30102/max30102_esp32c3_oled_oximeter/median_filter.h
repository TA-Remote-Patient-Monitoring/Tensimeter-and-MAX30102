#ifndef MEDIAN_FILTER_H_
#define MEDIAN_FILTER_H_

#include <algorithm>
#include <stddef.h>

template <typename T, size_t N>
class MedianFilter {
 public:
  explicit MedianFilter(T invalid_value)
      : invalid_value_(invalid_value), write_index_(0) {
    std::fill(values_, values_ + N, invalid_value_);
  }

  void push(T value) {
    values_[write_index_] = value;
    write_index_ = (write_index_ + 1) % N;
  }

  bool median(T* median_out) const {
    if (median_out == nullptr) return false;

    T valid_values[N];
    size_t valid_count = 0;
    for (size_t i = 0; i < N; ++i) {
      T value = values_[i];
      if (value != invalid_value_) valid_values[valid_count++] = value;
    }

    if (valid_count == 0) return false;

    std::sort(valid_values, valid_values + valid_count);
    if (valid_count % 2) {
      *median_out = valid_values[valid_count / 2];
    } else {
      *median_out =
          (valid_values[valid_count / 2 - 1] + valid_values[valid_count / 2]) /
          static_cast<T>(2);
    }
    return true;
  }

 private:
  T values_[N] = {};
  T invalid_value_;
  size_t write_index_;
};

#endif  // MEDIAN_FILTER_H_
