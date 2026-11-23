# 固定排列下最坏新增无空闲工期的文献对照

2026-11-22。对照模型固定作业排列和必设无空闲机器集合 \(S\)，再按正整数机器成本与预算选择附加集合 \(T\)，最大化 \(\Delta(T)=C_{\max}(S\cup T)-C_{\max}(S)\)。缓冲无限，初始机器可用时刻为绝对下界。提前换型与加工一起占用机器，且无需额外共享资源。下文对照以这些假设为准。

## 已有模型和数学结构

| 待核内容 | 一手先例与手稿定位 |
| --- | --- |
| 固定排列计算混合无空闲工期 | Pan 与 Ruiz 的 §3.2、式 (8)–(9) 已给普通行和连续加工行的递推，机器无空闲集合预给定。Bektaş、Hamzadayı 与 Ruiz 的 §2、式 (6)–(7) 已有相同连续性约束，§3 用 Benders 分解优化排列。固定排列递推及已知无空闲集合的模型应作为先行结果。 [Pan–Ruiz 作者稿](https://riunet.upv.es/server/api/core/bitstreams/fe35fffd-ddd3-43b4-a7d3-fff882584031/content) · [Bektaş 等](https://doi.org/10.1007/s10951-020-00637-8) |
| 作业释放向量和秩一机器 | Kubo 作者论文 §2.4.1–2.4.2、命题 2.4.5 和式 (2.22) 将任意作业释放向量写成 max-plus 输入。定理 2.4.7 的证明把每台无空闲机明确分解成秩一 max-plus 外积，并将相邻秩一因子收缩成标量。把普通机块夹在两台秩一机之间，收缩仍成立。标量检查点表示应从这一代数先例出发。 [Kubo 作者学位论文](https://repository.dl.itc.u-tokyo.ac.jp/record/52997/files/A34816.pdf) · [Kubo–Nishinari 期刊文章](https://doi.org/10.1016/j.dam.2018.03.045) |
| 首末机的无空闲标志 | Saadani 与 Baptiste 的命题 1 及其后文已有经典无释放模型的端点结论。第一台机器自然连续作业，最后一台的空闲可通过向右移除而不改变工期。任意作业释放时首台不再普遍免费。 [Saadani–Baptiste 作者稿](https://citeseerx.ist.psu.edu/document?doi=4ef5171b80f7cd1287ec1909e1a47423941b962b&repid=rep1&type=pdf) |
| 单次初始机器可用时刻 | Pérez González 与 Framinan 的 §2 已研究 \(F_m\lvert prmu,a_i\rvert C_{\max}\)，机器 \(i\) 自 \(a_i\) 起可用且无后续停机。他们研究排列最小化，并给出在其无换型模型内的可用时刻冗余规则。该规则迁移到提前换型模型需要额外推导。 [作者稿](https://idus.us.es/server/api/core/bitstreams/3821f35f-51a6-4c74-9a54-d88311f38564/content) · [期刊文章](https://doi.org/10.1016/j.cor.2008.12.018) |
| 提前换型及无空闲与换型并存 | Wang 与 Cheng 的 §§2–4 允许作业到达前换型，并处理一个维护窗口。其两机排列模型允许加工和换型恢复，研究绝对工期。Rossi 与 Nagano 研究有序列相关换型的混合无空闲总流动时间，其后续工作详述可空闲机的换型。Zeng 与 Cui 已把分布式混合无空闲和序列相关换型放进同一模型。提前换型与模型组合本身归入相关工作。 [Wang–Cheng 作者稿](https://ira.lib.polyu.edu.hk/bitstream/10397/652/1/Heuristics.pdf) · [Rossi–Nagano 2019](https://doi.org/10.1016/j.eswa.2019.01.057) · [Rossi–Nagano 后续](https://doi.org/10.1080/01605682.2019.1671149) · [Zeng–Cui](https://www.mdpi.com/2073-8994/17/2/276) |
| 反 Monge 的路径交换 | Imaev 的 §12.2 定理 12.2.4 已用交叉路径交换证明 max-plus 输入输出矩阵反 Monge，定理 12.2.7 证明相应的乘积闭合性，§12.4 给出排列流水车间应用。手稿证明的是由候选锁机位置定义的**机器索引区间矩阵** \(a(i,j)\)。 [Imaev 作者学位论文](https://etd.ohiolink.edu/acprod/odb_etd/ws/send_file/send?accession=ohiou1257871858&disposition=inline) |
| 外部时钟进入 max-plus 模型 | Baccelli 等的式 (1.10) 已把资源可用性作为外部输入，线性传播后取最大值。按源展开、在弧上传递 \(\max(x+a,b)\) 继承此代数。手稿中特定于锁机的实质是同区间内 \(b(i,j)\) 对候选前驱 \(i\) 单调，并据此把常数分支归并到最早可达前驱。 [Baccelli、Cohen、Olsder 与 Quadrat 专著](https://www.rocq.inria.fr/metalau/cohen/documents/BCOQ-book.pdf#page=22) |

## 直接算法对照

**通用项目网络方法。** Brown、Carlyle、Royset 与 Wood 的 §4、式 (28) 直接给预算限制下的最长路径式 MAXMAX1。Wu、Demeulemeester 与 Matuschke 的 §3.1.1 对单位单边费用给出 \(\mathcal O(k|E|)\) 的资源分层，对异成本给出背包障碍，§3.1.2 允许将路径上至多碰到一次的非重叠组归到单边情形。把作业位置图的各锁机反向弧作为一个机器组，每条路径在每一层最多走一条这种弧。对应的通用背包分层 DP 每台机器有 \(\mathcal O(n^2)\) 次弧松弛，整体 \(\mathcal O((B+1)mn^2)\)。手稿已有利用行内可分离性的 \(\mathcal O((B+1)mn)\) 专用 DP。二者和检查点法可在相同输入、整数预算、回溯规则下比较。通用模型要求的非负绝对弧权可用手稿现有位置图证明中的逐层平移，因为每条完整路径经过同数机器层。 [Brown 等作者全文](https://faculty.nps.edu/gbrown/docs/BrownCarlyleRoysetWood2005.pdf) · [Wu 等期刊记录](https://doi.org/10.1016/j.ejor.2026.10.024) · [Wu 等公开全文 v1](https://arxiv.org/html/2608.27386v1)

**Monge 检查点方法的直接经典原语。** Aggarwal、Schieber 与 Tokuyama 的最小权 \(k\)-边 Monge 路径，是单位锁机成本的近邻。对异成本，Galil 与 Park 的第 310–311 页、图 2 给出上三角全单调矩阵在线列最小值的线性算法，并明确支持多个在线实例交错运行。对每个已用预算 \(q\) 和每个必锁机间区间维护一个流，矩阵项取 \(-D_i(q)-a(i,j)\)。处理机器 \(j\) 时先查所有 \(q\) 的列 \(j\)，然后加上固定目的成本 \(c_j\)，更新得到 \(D_j(\cdot)\)，再向每个流公开新行。先查询后公开也覆盖免费的必锁端点。反 Monge 在加行常数并取负后给出所需性质。不可达行可用有限的足够大行平移并单独追踪可达性，从而保持 Monge 条件。绝对可用时刻的常数分支使用每个 \(q\) 的最早可达前驱。由此得预处理 \(\mathcal O(m^2n)\) 加每次预算查询 \(\mathcal O(m(B+1))\) 的理论实现路线，依赖预计算传递量的 \(\mathcal O(1)\) 读取。已写的 \(\log m\) 包络实现应按其已验证复杂度单列。 [Aggarwal 等期刊文章](https://doi.org/10.1007/BF02574380) · [Galil–Park 作者全文](https://gwern.net/doc/cs/algorithm/1990-galil.pdf) · [期刊记录](https://doi.org/10.1016/0020-0190(90)90215-J)

检查点路径把预算计算从作业位置维度中分离，其比较价值包括重复预算或成本查询。计入预处理后，与 \(\mathcal O((B+1)mn)\) 专用单查询法的相对快慢取决于 \(B,m,n\) 和查询数。

## 近似分界及保留的主张

- **绝对工期、工期净增和差分近似。** Ng 与 Kovalyov 对两机、一个不可用窗口的绝对工期最小化给出 FPTAS。在本文中，无锁方案给出绝对工期最大化的最坏可行值，因此净增比属于经典差分近似指标。把有保证的绝对工期减去基准会产生与基准有关的误差项。Wu 等 v1 的 §4.2 观察 4.1 已给一般项目网络中净增非次模例，数值为 \(5>2+2\)。 [Ng–Kovalyov](https://doi.org/10.1002/nav.10107) · [Demange–Paschos](https://doi.org/10.1016/0304-3975(95)00060-7) · [Wu 等 v1](https://arxiv.org/html/2608.27386v1)
- **对吴等绝对近似定理的引用边界。** 公开 v1 的定理 4.1 末行给绝对工期的 \(k\) 倍保证。证明的中间净增不等式被同文观察 4.1 的两组增量 \(5>2\times2\) 否定。这一判断限于公开 v1。绝对保证可沿最优路径重新证明，利用该路径的非负原始工期和每个单组在同一路径上的增量之和。 [Wu 等 v1 §§4.1–4.2](https://arxiv.org/html/2608.27386v1)
- **最强的模型特定区分。** 对单个固定排列、两作业、正加工时长，内部机器锁选择实现异成本背包奖励，单个末机初始时钟可把工期净增变成 \(\max(0,\sum_{i\in T}v_i-H+1)\)。因此任何有限乘法保证都会判定是否存在严格正净增。通用项目最长路径已有背包硬度，竞争基准路径截断也是通用机制。此次未找到把这个不可近似性门槛用上述合法两作业流水车间结构和**唯一末机绝对时钟**实现的一手先例。一个末机等值提前初始换型的同类实现也暂未查到直接结果。困难性限于净增目标和正整数异成本，条件为 \(P\ne NP\)。 [Brown 等 §4](https://faculty.nps.edu/gbrown/docs/BrownCarlyleRoysetWood2005.pdf) · [Wu 等 §3](https://arxiv.org/html/2608.27386v1)
- **源松弛的条件近似。** 若 \(F_h(T)\) 是源 \(h\) 的齐次末工期贡献，置 \(d_h=C_{\max}(S)-F_h(\varnothing)\)，\(G_h=\max_T[F_h(T)-F_h(\varnothing)]\)，则 \(\Delta^\star=\max_h(G_h-d_h)\)。若各源单独可作相对误差 \(\eta\) 的近似，且至少一个最优源满足 \(d_h\le\rho\Delta^\star\)，取 \(\eta=\varepsilon/(1+\rho)\) 即给出净增 \(1-\varepsilon\) 保证，算法需比较各源返回的实际可行锁集合。运行时间对数值 \(1+\rho\) 和 \(1/\varepsilon\) 为多项式。由各源上下界分别减去 \(d_h\) 后取最大值得通用最优值区间。最优源的存在性承诺和事后认证计算量应分别表述。源传播与差分近似各有先例，本轮未找到把这一源松弛参数用于相同预算锁机问题的直接结果。 [Baccelli 等](https://www.rocq.inria.fr/metalau/cohen/documents/BCOQ-book.pdf#page=22) · [Demange–Paschos](https://doi.org/10.1016/0304-3975(95)00060-7) · [Hassin 的受限路径近似](https://doi.org/10.1287/moor.17.1.36)

以机器索引为轴的区间反 Monge、锁机预算内的绝对常数分支单调性、共用一个末机时钟的复杂度分界和有条件的源松弛保证，是这一轮最值得保留并精确归因的定理。现有流水车间定序算法、网络表示、max-plus 秩一和在线矩阵查询提供必要的已知组成部分。通用路径的预算模型与在线矩阵查询应明确作为直接对照。

## 检索边界

公开的一手论文、作者学位论文和可访问全文优先。按 mixed no-idle permutation flowshop、fixed sequence no-idle rank one max-plus、machine availability initial date、anticipatory sequence-dependent setup、budgeted project makespan interdiction、heterogeneous-cost Monge path、positive makespan increase differential approximation、source slack approximation 等关键词检索，并追查直接相邻文章的引用。Kubo 的具体命题以作者学位论文为准。Wu 等的章节定位使用公开 v1，正式刊版的全文表述尚未比对。本轮覆盖可得公开材料，未索引或不可访问的手稿仍可能有重叠，因此保留“本次未找到直接先例”的措辞。未访问实验留出数据。

补查任意删钟与固定排列的近邻工作。2025 年的工序跨阶段分配研究在两作业或两机器的定序特例给出多项式算法，优化可跨阶段分配的加工工序。近期固定输出顺序的紧耦合生产线研究允许返入、换型和相对期限，优化作业在各工位的安排。两类都是实质相关的固定顺序研究。这次检索尚未找到在同一固定排列上，对预算可选无空闲模式求任意删钟的最大工期误差，并用共同的强制基准阈值维护机器索引上包络的直接先例。 [跨阶段分配](https://doi.org/10.1016/j.cor.2025.107219) · [紧耦合生产线](https://doi.org/10.1007/s10845-025-02766-3)
