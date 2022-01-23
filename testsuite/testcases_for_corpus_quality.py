# Copyright 2022 @ReneFreingruber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# TODO check if the operations store the return values of function invocations in variables
# E.g.: var var_1_ = [1,2,3];
# If the operational-database contains an entry like:
# var_1_.pop();
# This would be bad because the result of .pop() is not stored in a variable
# => I would need to rewrite it to:
# var var_2_ = var_1_.pop();

# TODO remove the spaces and tabs when checking.
# and change " to ' and ' to "


# TODO:
# "catch ({var_" in some operation
# see CVE-2017-8656

# TODO:
# return var_TARGET_
# => This can't be in the database because it will always throw an exception in my testing code



expected_operations_in_database = [
    ("Object.preventExtensions(var_TARGET_", "any"),        # Chromium issue 992914
    ("Object.seal(var_TARGET_", "any"),                     # Chromium issue 992914
    ("var_TARGET_.__proto__ = 0", "any"),                   # Chromium issue 992914
    ("var_TARGET_.__proto__ =", "any"),                     # CVE-2019-11707, Firefox bug 1544386
    ("var_TARGET_.__proto__ = {}", "any"),                  # CVE-2019-9813, Firefox bug 1538006
    ("var_TARGET_.prototype =", "any"),                     # CVE-2019-0539, Edge
    ("var_TARGET_.map(", "array"),                          # CVE-2018-4192, Safari
    ("var_TARGET_.reverse(", "array"),                      # CVE-2016-3386, Safari CVE-2018-4192
    ("var_TARGET_.push(", "array"),                         # Chromium issue 716044
    ("var_TARGET_.slice(", "array"),                        # Safari CVE-2016-4622
    ("var_TARGET_.indexOf(", "array"),                      # CVE-2017-5053, Chromium issue 702058
    ("var_TARGET_.fill(", "array"),                         # Chromium issue 938251
    ("var_TARGET_.concat(", "array"),                       # CVE-2017-5030, Chromium issue 682194
    ("var_TARGET_.sort(", "array"),                         # Chromium issue 852592
    ("var_TARGET_.includes(", "array"),                     # Chromium issue 944062
    ("var_TARGET_.pop(", "array"),                          # CVE-2019-11707, Firefox bug 1544386
    ("var_TARGET_.shift(", "array"),                        # CVE-2014-7928
    ("var_TARGET_.join(", "array"),                         # CVE-2016-7189
    ("var_TARGET_.splice(", "array"),                       # CVE-2017-2464
    ("[...var_TARGET_", "array"),                           # CVE-2016-7194

    ("var_TARGET_ = +var_TARGET_", "array"),                # CVE-2017-11840; TODO this operation should also be there for other data types (?),
    ("var_TARGET_ = +var_TARGET_", "string"),               # CVE-2018-0770
    ("var_TARGET_.localeCompare(", "string"),               # CVE-2018-8355
    (".localeCompare(var_TARGET_", "string"),               # CVE-2018-8355

    ("var_TARGET_[", "array"),

    ("delete var_TARGET_[", "array"),                       # CVE-2018-6064
    ("var_TARGET_.length =", "array"),                      # CVE-2018-6064
    ("var_TARGET_.length", "array"),                        # CVE-2018-6064; TODO: This also includes the above one, so the above one would be useless?
    ("var_TARGET_.unshift(", "array"),                      # CVE-2018-6064
    ("Object.entries(var_TARGET_)", "array"),               # CVE-2018-6064
    ("new Map(var_TARGET_)", "array"),                      # CVE-2018-6142

    ("var_TARGET_ +=", "real_number"),                      # CVE-2018-0769, Edge
    ("var_TARGET_ -=", "real_number"),                      # similar as above
    ("var_TARGET_ *=", "real_number"),
    ("var_TARGET_ /=", "real_number"),
    ("var_TARGET_ %=", "real_number"),
    ("var_TARGET_ &=", "real_number"),                      # CVE-2017-5115, Chromium issue 744584
    ("var_TARGET_ |=", "real_number"),

    ("var_TARGET_ | ", "real_number"),                      # CVE-2017-8645, CVE-2017-8646,
    # TODO: but there should be no "=" afterwards, so I need "|" and not "|=";
    #  the space misses stuff like "var_TARGET_|5"
    # => TODO: I also always have a space in front like "var_TARGET_+=" would also not be detected because I just check for "var_TARGET_ +="

    ("var_TARGET_ ===", "real_number"),                     # CVE-2018-0777
    ("var_TARGET_ += 0", "real_number"),                    # CVE-2018-0777

    ("new Array(var_TARGET_)", "real_number"),              # CVE-2017-2521
    ("var_TARGET_.toExponential(", "real_number"),          # CVE-2019-0930

    ("var_TARGET_ !==", "any"),                             # CVE-2018-8355

    ("var_TARGET_ +", "real_number"),
    ("var_TARGET_ -", "real_number"),
    ("var_TARGET_ *", "real_number"),
    ("var_TARGET_ /", "real_number"),
    ("var_TARGET_++", "real_number"),
    ("++var_TARGET_", "real_number"),
    ("var_TARGET_--", "real_number"),
    ("--var_TARGET_", "real_number"),

    ("var_TARGET_ >>=", "real_number"),                     # Chromium issue 762874

    ("Math.expm1(var_TARGET_", "real_number"),              # Chromium issue 880207
    ("Math.sign(var_TARGET_", "real_number"),               # CVE-2016-5200, Chromium issue 658114
    ("Math.max(var_TARGET_", "real_number"),                # CVE-2019-9793, Firefox bug 1528829
    ("Math.min(var_TARGET_", "real_number"),                # similar as above
    (".charCodeAt(var_TARGET_", "real_number"),             # CVE-2019-9793, Firefox bug 1528829

    ("var_TARGET_.charCodeAt(", "string"),                  # CVE-2019-9793, Firefox bug 1528829
    ("var_TARGET_.charAt(", "string"),                      # CVE-2018-4442
    ("var_TARGET_.match(", "string"),                       # CVE-2016-1669
    ("var_TARGET_.split(", "string"),                       # CVE-2018-6149
    ("var_TARGET_.toLocaleString(", "string"),              # CVE-2016-7286
    ("var_TARGET_.replace(", "string"),                     # CVE-2017-11802
    ("var_TARGET_.repeat(", "string"),                      # CVE-2018-0758
    ("var_TARGET_.length", "string"),                       # CVE-2018-0758
    ("var_TARGET_.link(", "string"),                        # CVE-2017-7092
    (".link(var_TARGET_", "string"),                        # CVE-2017-7092

    ("in var_TARGET_", "string"),                           # CVE-2019-5784; code like: for (var var_1_ in var_TARGET_) {
    ("in var_TARGET_", "array"),                            # CVE-2019-5784

    ("var_TARGET_ + ''", "string"),                         # CVE-2018-4382; but it could also be " instead of '

    ("delete var_TARGET_.", "any"),                         # CVE-2019-5784; deleting a property

    (".match(var_TARGET_", "regexp"),                       # CVE-2016-1669
    ("var_TARGET_.lastIndex", "regexp"),                    # CVE-2018-6056
    ("var_TARGET_.test(", "regexp"),                        # CVE-2019-8558
    (".test(var_TARGET_", "string"),                        # CVE-2019-8558
    ("var_TARGET_.compile(", "regexp"),                     # CVE-2017-11890
    (".compile(var_TARGET_", "string"),                     # CVE-2017-11890
    ("var_TARGET_ ?", "boolean"),                           # CVE-2019-5755, Chromium issue 913296
    ("var_TARGET_ = true", "boolean"),
    ("var_TARGET_ = false", "boolean"),

    # TODO also for int8array and so on...
    ("var_TARGET_.subarray(", "uint8array"),                # CVE-2014-1513, Firefox bug 982974
    ("var_TARGET_.subarray(", "uint32array"),               # CVE-2014-1513
    ("var_TARGET_.map(", "uint8array"),                     # CVE-2015-6771
    ("var_TARGET_.fill(", "uint8array"),                    # CVE-2017-5040
    ("var_TARGET_.sort(", "uint8array"),                    # CVE-2016-7288
    ("var_TARGET_.copyWithin(", "uint8array"),              # CVE-2016-4734
    (".copyWithin(var_TARGET_", "real_number"),             # CVE-2016-4734
    ("var_TARGET_.constructor =", "uint8array"),            # CVE-2015-6771
    ("var_TARGET_.constructor.prototype =", "uint8array"),  # CVE-2015-6771
    ("var_TARGET_.of(", "bigint64array"),                   # CVE-2018-16065, Chromium issue 867776

    ("new Float64Array(var_TARGET_)", "any"),               # CVE-2013-6632
    ("new Uint32Array(var_TARGET_)", "any"),                # CVE-2014-1705
    ("Object.create(var_TARGET_", "any"),                   # CVE-2018-17463, Chromium issue 888923
    ("Object.create(var_TARGET_)", "any"),                  # CVE-2018-17463, Chromium issue 888923
    ("JSON.stringify(var_TARGET_", "any"),                  # CVE-2015-6764, Chromium issue 554946,

    ("var_TARGET_.valueOf = function", "any"),              # CVE-2016-4622, Safari
    ("Object.defineProperty(var_TARGET_", "any"),           # CVE-2016-1646, CVE-2019-8506, Chromium issue 594574
    ("Object.setPrototypeOf(var_TARGET_", "array"),         # CVE-2019-8506
    ("var_TARGET_.__defineGetter__(", "any"),               # CVE-2014-1705, Chromium issue 351787
    ("var_TARGET_.apply(", "function"),                     # CVE-2019-5782, Chromium issue 906043
    ("var_TARGET_.toString(", "function"),                  # CVE-2016-1688
    ("var_TARGET_.bind(", "function"),                      # CVE-2018-8139
    ("var_TARGET_.caller", "function"),                     # CVE-2017-2446
    ("var_TARGET_.concat(", "string"),                      # CVE-2014-3176, Chromium issue 386988
    (".concat(var_TARGET_", "any"),                         # CVE-2014-3176, Chromium issue 386988, not 100% required but would be nice to have
    ("var_TARGET_.search(", "string"),                      # CVE-2017-11906
    (".search(var_TARGET_", "regexp"),                      # CVE-2017-11906

    (" extends var_TARGET_", "any"),                        # CVE-2019-0539, Edge
    ("Object.is(var_TARGET_", "any"),                       # Chromium issue 880207

    ("typeof(var_TARGET_", "any"),                          # CVE-2018-0840
    ("Intl.NumberFormat.apply(var_TARGET_", "any"),         # CVE-2018-8298
    ("Intl.DateTimeFormat.apply(var_TARGET_", "any"),       # CVE-2018-8298
    ("Intl.DateTimeFormat.prototype.formatToParts.apply(var_TARGET_", "any"),     # CVE-2018-8298



    # TODO: Make this testcase compatible with other JS engines?
    ("gc()", "any"),                                        # Triggering garbage collection is required in a lot of exploits;

    ("async function", "any"),

    ("parseInt()", "any"),                                  # CVE-2016-5198, Chromium issue 659475
    ("Array(", "any"),                                      # CVE-2019-5825, Chromium issue 941743
    ("eval(", "any"),                                       # CVE-2019-9813, Firefox bug 1538006
    ("parseFloat(", "any"),                                 # CVE-2018-6142
    ("Reflect.construct(", "any"),                          # CVE-2020-6418, Chromium issue 1053604
    ("decodeURI(", "any"),                                  # CVE-2016-1677
    ("Intl = {}", "any"),                                   # CVE-2016-7287

    ("Reflect.construct(", "any"),                          # CVE-2020-6418, Chromium issue 1053604
    ("BigInt64Array.of.call", "any"),                       # CVE-2018-16065, Chromium issue 867776
    ("Object.assign(", "any"),                              # CVE-2016-9651, Chromium issue 664411
    ("RegExp.lastParen", "any"),                            # CVE-2017-11906; it's accessed after a call to e.g. .search()
    ("RegExp.input", "any"),                                # CVE-2018-0891
    ("RegExp.lastMatch", "any"),                            # CVE-2018-0891
    ("parseFloat(", "any"),                                 # CVE-2018-6142
]
