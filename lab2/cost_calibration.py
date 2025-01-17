import joblib
import numpy as np
from sklearn.linear_model import LinearRegression


def estimate_plan(operator, factors, weights):
    cost = 0.0
    for child in operator.children:
        cost += estimate_plan(child, factors, weights)

    if operator.is_hash_agg():
        # YOUR CODE HERE: hash_agg_cost = input_row_cnt * cpu_fac
        input_row_cnt = operator.est_row_counts()
        cost += input_row_cnt * factors['cpu']
        weights['cpu'] += input_row_cnt

    elif operator.is_hash_join():
        # YOUR CODE HERE:
        # hash_join_cost = (build_hashmap_cost + probe_and_pair_cost)
        #   = (build_row_cnt * cpu_fac) + (output_row_cnt * cpu_fac)
        output_row_cnt = operator.est_row_counts()
        build_side = int(operator.children[1].is_build_side())
        build_row_cnt = operator.children[build_side].est_row_counts()

        cost += (build_row_cnt + output_row_cnt) * factors['cpu']
        weights['cpu'] += (build_row_cnt + output_row_cnt)

    elif operator.is_sort():
        # YOUR CODE HERE: sort_cost = input_row_cnt * log(input_row_cnt) * cpu_fac
        input_row_cnt = operator.est_row_counts()
        cost += input_row_cnt * np.log(input_row_cnt + 1e-10) * factors['cpu']
        weights['cpu'] += input_row_cnt * np.log(input_row_cnt + 1e-10)

    elif operator.is_selection():
        # YOUR CODE HERE: selection_cost = input_row_cnt * cpu_fac
        input_row_cnt = operator.est_row_counts()
        cost += input_row_cnt * factors['cpu']
        weights['cpu'] += input_row_cnt

    elif operator.is_projection():
        # YOUR CODE HERE: projection_cost = input_row_cnt * cpu_fac
        input_row_cnt = operator.est_row_counts()
        cost += input_row_cnt * factors['cpu']
        weights['cpu'] += input_row_cnt

    elif operator.is_table_reader():
        # YOUR CODE HERE: table_reader_cost = input_row_cnt * input_row_size * net_fac
        input_row_cnt = operator.est_row_counts()
        input_row_size = operator.row_size()
        cost += input_row_cnt * input_row_size * factors['net']
        weights['net'] += input_row_cnt * input_row_size

    elif operator.is_table_scan():
        # YOUR CODE HERE: table_scan_cost = row_cnt * row_size * scan_fac
        row_cnt = operator.est_row_counts()
        row_size = operator.row_size()
        cost += row_cnt * row_size * factors['scan']
        weights['scan'] += row_cnt * row_size

    elif operator.is_index_reader():
        # YOUR CODE HERE: index_reader_cost = input_row_cnt * input_row_size * net_fac
        input_row_cnt = operator.est_row_counts()
        input_row_size = operator.row_size()
        cost += input_row_cnt * input_row_size * factors['net']
        weights['net'] += input_row_cnt * input_row_size

    elif operator.is_index_scan():
        # YOUR CODE HERE: index_scan_cost = row_cnt * row_size * scan_fac
        row_cnt = operator.est_row_counts()
        row_size = operator.row_size()
        cost += row_cnt * row_size * factors['scan']
        weights['scan'] += row_cnt * row_size

    elif operator.is_index_lookup():
        # YOUR CODE HERE:
        # index_lookup_cost = net_cost + seek_cost
        #   = (build_row_cnt * build_row_size + probe_row_cnt * probe_row_size) * net_fac +
        #     (build_row_cnt / batch_size) * seek_fac
        build_side = int(operator.children[1].is_build_side())
        build_row_cnt = operator.children[build_side].est_row_counts()
        build_row_size = operator.children[build_side].row_size()
        probe_row_cnt = operator.children[1 - build_side].est_row_counts()
        probe_row_size = operator.children[1 - build_side].row_size()
        batch_size = operator.batch_size()

        cost += (build_row_cnt * build_row_size + probe_row_cnt * probe_row_size) * factors['net']
        weights['net'] += (build_row_cnt * build_row_size + probe_row_cnt * probe_row_size)

        cost += (build_row_cnt / batch_size) * factors['seek']
        weights['seek'] += (build_row_cnt / batch_size)

    else:
        print(operator.id)
        assert (1 == 2)  # unknown operator
    return cost


# 准备回归训练的数据
def prepare_train_data(factors, weights, act_times):
    X_train = []
    y_train = []
    for weight in weights:
        weight_array = []
        for k, v in weight.items():
            v *= factors[k]
            weight_array.append(v)
        weight_array = np.array(weight_array).astype(np.float32)
        X_train.append(weight_array)
    y_train = np.array(act_times).astype(np.float32)
    return np.nan_to_num(X_train), np.nan_to_num(y_train)


def estimate_calibration(train_plans, test_plans):
    # init factors
    factors = {
        "cpu": 1,
        "scan": 1,
        "net": 1,
        "seek": 1,
    }

    # get training data: factor weights and act_time
    est_costs_before = []
    act_times = []
    weights = []
    for p in train_plans:
        w = {"cpu": 0, "scan": 0, "net": 0, "seek": 0}
        cost = estimate_plan(p.root, factors, w)
        weights.append(w)
        act_times.append(p.exec_time_in_ms())
        est_costs_before.append(cost)

    # YOUR CODE HERE
    # calibrate your cost model with regression and get the best factors
    # factors * weights ==> act_time
    linreg = LinearRegression()
    X_train, y_train = prepare_train_data(factors, weights, act_times)
    linreg.fit(X_train, y_train)
    joblib.dump(linreg, "data/lab2-linreg.pkl")
    new_factors = {}
    new_factors['cpu'] = linreg.coef_.data[0]
    new_factors['scan'] = linreg.coef_.data[1]
    new_factors['net'] = linreg.coef_.data[2]
    new_factors['seek'] = linreg.coef_.data[3]
    print("--->>> regression cost factors: ", new_factors)

    # evaluation
    est_costs = []
    for p in test_plans:
        w = {"cpu": 0, "scan": 0, "net": 0, "seek": 0}
        cost = estimate_plan(p.root, new_factors, w)
        est_costs.append(cost)

    return est_costs
